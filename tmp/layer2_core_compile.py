"""Layer-2 structural deterioration detection for MCIFT.

Layer 2 treats the Layer-1B healthy graph as frozen. It does not add, remove,
or reinterpret topology while evaluating a run. Its job is to measure departure
from healthy node and relationship behavior and emit persistent warning episodes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable
import warnings

import numpy as np

from mcift.discovery import DiscoveryResult, HealthyCalibrationResult
from mcift.profiling import (
    EvidenceItem,
    EvidenceStatus,
    Outcome,
    Profile,
    Router,
    evaluate_profile,
)


FEATURE_NAMES = (
    "edge_loss_fraction",
    "edge_outside_fraction",
    "node_center_outlier_fraction",
    "node_scale_outlier_fraction",
    "missingness_outlier_fraction",
)


@dataclass(frozen=True)
class DetectionConfig:
    window_size: int = 256
    step_size: int = 64
    min_overlap: int = 80
    warning_quantile: float = 0.99
    confirmation_quantile: float = 1.0
    persistence_windows: int = 2
    healthy_history_windows: int = 2
    threshold_epsilon: float = 1e-9
    edge_lower_quantile: float = 0.05
    edge_upper_quantile: float = 0.95
    node_lower_quantile: float = 0.01
    node_upper_quantile: float = 0.99
    variance_floor: float = 1e-12
    clip_z: float = 8.0


@dataclass(frozen=True)
class WarningWindow:
    window_index: int
    start_row: int
    end_row: int
    score: float
    threshold: float
    above_threshold: bool
    profiler_outcome: str
    features: tuple[float, ...]
    feature_z: tuple[float, ...]


@dataclass(frozen=True)
class WarningEpisode:
    start_window: int
    end_window: int
    start_row: int
    end_row: int
    confirm_window: int
    confirm_row: int
    max_score: float
    classification: str


@dataclass(frozen=True)
class HealthyOperationalBaseline:
    frozen_edges: int
    backbone_groups: int
    node_groups: int
    edge_q_low: tuple[float, ...]
    edge_q_high: tuple[float, ...]
    node_center_q_low: tuple[float, ...]
    node_center_q_high: tuple[float, ...]
    node_scale_q_low: tuple[float, ...]
    node_scale_q_high: tuple[float, ...]
    node_missing_q_high: tuple[float, ...]
    feature_median: tuple[float, ...]
    feature_scale: tuple[float, ...]
    score_threshold: float
    window_quantile_threshold: float
    threshold_method: str
    confirmation_quantile: float
    healthy_windows: int
    healthy_run_stats: tuple[dict, ...]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class DetectionResult:
    run_id: str
    rows: int
    column_coverage: float
    windows: tuple[WarningWindow, ...]
    episodes: tuple[WarningEpisode, ...]
    first_episode_start_window: int | None
    first_confirm_window: int | None
    first_deterioration_start_window: int | None
    first_deterioration_confirm_window: int | None
    baseline: HealthyOperationalBaseline

    def to_dict(self) -> dict:
        return {
            "scope": {
                "layer": "structural_departure_detection",
                "frozen_layer1_backbone": True,
                "discovers_new_edges": False,
                "context_edges_in_warning_score": False,
                "uses_anomaly_labels_for_threshold": False,
                "causal_claim": False,
            },
            "run_id": self.run_id,
            "rows": self.rows,
            "column_coverage": self.column_coverage,
            "feature_names": list(FEATURE_NAMES),
            "baseline": self.baseline.to_dict(),
            "windows": [asdict(x) for x in self.windows],
            "episodes": [asdict(x) for x in self.episodes],
            "first_episode_start_window": self.first_episode_start_window,
            "first_confirm_window": self.first_confirm_window,
            "first_deterioration_start_window": (
                self.first_deterioration_start_window
            ),
            "first_deterioration_confirm_window": (
                self.first_deterioration_confirm_window
            ),
        }


@dataclass
class _MeasuredRun:
    run_id: str
    rows: int
    coverage: float
    ends: np.ndarray
    edge: np.ndarray
    center: np.ndarray
    scale: np.ndarray
    missing: np.ndarray


class Layer2Detector:
    """Fit operational healthy envelopes and detect structural departure.

    The topology comes exclusively from Layer 1B frozen edges. Healthy runs are
    used to calibrate shorter operational windows and the warning threshold.
    """

    def __init__(
        self,
        discovery: DiscoveryResult,
        discovery_source_columns: Iterable[str],
        calibration: HealthyCalibrationResult,
        *,
        config: DetectionConfig | None = None,
    ) -> None:
        self.discovery = discovery
        self.calibration = calibration
        self.config = config or DetectionConfig()
        self.discovery_source_columns = tuple(discovery_source_columns)

        if len(self.discovery_source_columns) != discovery.n_channels:
            raise ValueError(
                "discovery_source_columns must match discovery.n_channels"
            )
        if not calibration.frozen_edges:
            raise ValueError(
                "Layer 2 requires at least one frozen healthy edge"
            )

        self._channel_source = {
            f"C{i + 1:04d}": source
            for i, source in enumerate(self.discovery_source_columns)
        }
        self._members: dict[str, list[str]] = {}
        for node in discovery.hierarchy:
            self._members.setdefault(
                node.redundancy_group, []
            ).append(node.channel)

        self._frozen = tuple(calibration.frozen_edges)
        self._groups = tuple(
            sorted(
                {e.source_group for e in self._frozen}
                | {e.target_group for e in self._frozen}
            )
        )
        self._group_pos = {
            group: i for i, group in enumerate(self._groups)
        }

        node_by_channel = {
            node.channel: node
            for node in calibration.nodes
        }
        self._representative: dict[str, str] = {}
        for group in self._groups:
            candidates = [
                channel
                for channel in self._members.get(group, ())
                if (
                    channel in node_by_channel
                    and node_by_channel[channel].profiler_outcome
                    == Outcome.CLOSE.value
                )
            ]
            if not candidates:
                continue
            self._representative[group] = (
                group
                if group in candidates
                else sorted(candidates)[0]
            )

        self._node_groups = tuple(
            sorted(self._representative)
        )

        needed = set(self._representative.values())
        for group in self._groups:
            needed.update(self._members.get(group, ()))

        self._needed_channels = tuple(
            sorted(
                channel
                for channel in needed
                if channel in self._channel_source
            )
        )
        self._needed_pos = {
            channel: i
            for i, channel in enumerate(self._needed_channels)
        }

        self._edge_source = np.asarray(
            [
                self._group_pos[e.source_group]
                for e in self._frozen
            ],
            dtype=int,
        )
        self._edge_target = np.asarray(
            [
                self._group_pos[e.target_group]
                for e in self._frozen
            ],
            dtype=int,
        )
        self._edge_lag = np.asarray(
            [
                int(
                    e.lag_mode
                    if e.lag_mode is not None
                    else e.discovery_lag
                )
                for e in self._frozen
            ],
            dtype=int,
        )
        self._node_idx = np.asarray(
            [
                self._needed_pos[self._representative[group]]
                for group in self._node_groups
            ],
            dtype=int,
        )

        self._healthy: list[_MeasuredRun] = []
        self.baseline: HealthyOperationalBaseline | None = None

    def _align(
        self,
        values: np.ndarray,
        source_columns: Iterable[str],
    ) -> tuple[np.ndarray, float]:
        matrix = np.asarray(values, dtype=float)
        columns = tuple(source_columns)

        if (
            matrix.ndim != 2
            or matrix.shape[1] != len(columns)
        ):
            raise ValueError(
                "run matrix/column shape mismatch"
            )

        run_map = {
            name: i
            for i, name in enumerate(columns)
        }
        out = np.full(
            (
                matrix.shape[0],
                len(self._needed_channels),
            ),
            np.nan,
            dtype=float,
        )

        matched = 0
        for channel, out_idx in self._needed_pos.items():
            source = self._channel_source[channel]
            idx = run_map.get(source)
            if idx is not None:
                out[:, out_idx] = matrix[:, idx]
                matched += 1

        return (
            out,
            matched / max(1, len(self._needed_channels)),
        )

    def _standardize(
        self,
        x: np.ndarray,
    ) -> np.ndarray | None:
        finite = np.isfinite(x)
        if int(finite.sum()) < 2:
            return None

        values = x[finite]
        center = float(np.median(values))
        mad = float(
            np.median(np.abs(values - center))
        )
        scale = 1.4826 * mad

        if scale <= self.config.variance_floor:
            scale = float(np.std(values))
        if scale <= self.config.variance_floor:
            return None

        out = np.full(
            x.shape,
            np.nan,
            dtype=float,
        )
        z = np.clip(
            (values - center) / scale,
            -self.config.clip_z,
            self.config.clip_z,
        )
        z -= float(np.mean(z))
        std = float(np.std(z))
        if std <= self.config.variance_floor:
            return None

        out[finite] = z / std
        return out

    def _group_matrix(
        self,
        aligned: np.ndarray,
    ) -> np.ndarray:
        result = np.full(
            (
                aligned.shape[0],
                len(self._groups),
            ),
            np.nan,
            dtype=float,
        )

        for gi, group in enumerate(self._groups):
            rows = []
            for channel in self._members.get(group, ()):
                idx = self._needed_pos.get(channel)
                if idx is None:
                    continue
                z = self._standardize(
                    aligned[:, idx]
                )
                if z is not None:
                    rows.append(z)

            if rows:
                with warnings.catch_warnings():
                    warnings.simplefilter(
                        "ignore",
                        category=RuntimeWarning,
                    )
                    result[:, gi] = np.nanmedian(
                        np.vstack(rows),
                        axis=0,
                    )

        return result

    def _edge_strengths(
        self,
        groups: np.ndarray,
        lo: int,
        hi: int,
    ) -> np.ndarray:
        result = np.full(
            len(self._frozen),
            np.nan,
            dtype=float,
        )

        for lag in np.unique(self._edge_lag):
            mask_edge = self._edge_lag == lag
            edge_indices = np.where(mask_edge)[0]

            a = groups[
                lo:hi,
                self._edge_source[edge_indices],
            ]
            b = groups[
                lo:hi,
                self._edge_target[edge_indices],
            ]

            if lag > 0:
                a, b = a[:-lag], b[lag:]
            elif lag < 0:
                shift = -lag
                a, b = (
                    a[shift:],
                    b[:-shift],
                )

            valid = np.isfinite(a) & np.isfinite(b)
            n = valid.sum(axis=0)

            aa = np.where(valid, a, 0.0)
            bb = np.where(valid, b, 0.0)

            ma = aa.sum(axis=0) / np.maximum(n, 1)
            mb = bb.sum(axis=0) / np.maximum(n, 1)

            da = np.where(
                valid,
                a - ma[None, :],
                0.0,
            )
            db = np.where(
                valid,
                b - mb[None, :],
                0.0,
            )

            cov = (da * db).sum(axis=0)
            denom = np.sqrt(
                (da * da).sum(axis=0)
                * (db * db).sum(axis=0)
            )

            ok = (
                (n >= self.config.min_overlap)
                & (
                    denom
                    > self.config.variance_floor
                )
            )

            values = np.full(
                len(edge_indices),
                np.nan,
                dtype=float,
            )
            values[ok] = np.abs(
                cov[ok] / denom[ok]
            )
            result[edge_indices] = values

        return result

    def _measure(
        self,
        values: np.ndarray,
        source_columns: Iterable[str],
        run_id: str,
    ) -> _MeasuredRun:
        aligned, coverage = self._align(
            values,
            source_columns,
        )
        groups = self._group_matrix(aligned)
        nodes = aligned[:, self._node_idx]

        ends = np.arange(
            self.config.window_size - 1,
            aligned.shape[0],
            self.config.step_size,
            dtype=int,
        )

        edge = np.empty(
            (
                len(ends),
                len(self._frozen),
            ),
            dtype=float,
        )
        center = np.empty(
            (
                len(ends),
                len(self._node_idx),
            ),
            dtype=float,
        )
        scale = np.empty_like(center)
        missing = np.empty_like(center)

        for wi, end in enumerate(ends):
            lo = (
                end
                - self.config.window_size
                + 1
            )
            hi = end + 1

            edge[wi] = self._edge_strengths(
                groups,
                lo,
                hi,
            )

            x = nodes[lo:hi]
            with warnings.catch_warnings():
                warnings.simplefilter(
                    "ignore",
                    category=RuntimeWarning,
                )
                med = np.nanmedian(
                    x,
                    axis=0,
                )
                mad = np.nanmedian(
                    np.abs(
                        x - med[None, :]
                    ),
                    axis=0,
                )
                std = np.nanstd(
                    x,
                    axis=0,
                )

            robust = 1.4826 * mad
            robust = np.where(
                robust
                > self.config.variance_floor,
                robust,
                std,
            )

            center[wi] = med
            scale[wi] = robust
            missing[wi] = np.mean(
                ~np.isfinite(x),
                axis=0,
            )

        return _MeasuredRun(
            run_id=run_id,
            rows=aligned.shape[0],
            coverage=coverage,
            ends=ends,
            edge=edge,
            center=center,
            scale=scale,
            missing=missing,
        )

    def add_healthy_run(
        self,
        values: np.ndarray,
        source_columns: Iterable[str],
        *,
        run_id: str,
    ) -> None:
        if self.baseline is not None:
            raise RuntimeError(
                "baseline already finalized"
            )
        if any(
            run.run_id == run_id
            for run in self._healthy
        ):
            raise ValueError(
                f"duplicate healthy run_id: {run_id}"
            )

        self._healthy.append(
            self._measure(
                values,
                source_columns,
                run_id,
            )
        )

    @staticmethod
    def _q(
        values: np.ndarray,
        q: float,
    ) -> np.ndarray:
        with warnings.catch_warnings():
            warnings.simplefilter(
                "ignore",
                category=RuntimeWarning,
            )
            return np.nanquantile(
                values,
                q,
                axis=0,
            )

    @staticmethod
    def _fractions(
        measured: _MeasuredRun,
        edge_low,
        edge_high,
        center_low,
        center_high,
        scale_low,
        scale_high,
        missing_high,
    ) -> np.ndarray:
        e = measured.edge
        c = measured.center
        s = measured.scale
        m = measured.missing

        ef = np.isfinite(e)
        cf = np.isfinite(c)
        sf = np.isfinite(s)
        mf = np.isfinite(m)

        low = (
            (e < edge_low[None, :])
            & ef
        )
        outside = (
            low
            | (
                (e > edge_high[None, :])
                & ef
            )
        )

        center_out = (
            (
                (c < center_low[None, :])
                | (c > center_high[None, :])
            )
            & cf
        )
        scale_out = (
            (
                (s < scale_low[None, :])
                | (s > scale_high[None, :])
            )
            & sf
        )
        missing_out = (
            (
                m
                > missing_high[None, :]
                + 1e-12
            )
            & mf
        )

        return np.column_stack(
            [
                low.sum(axis=1)
                / np.maximum(
                    1,
                    ef.sum(axis=1),
                ),
                outside.sum(axis=1)
                / np.maximum(
                    1,
                    ef.sum(axis=1),
                ),
                center_out.sum(axis=1)
                / np.maximum(
                    1,
                    cf.sum(axis=1),
                ),
                scale_out.sum(axis=1)
                / np.maximum(
                    1,
                    sf.sum(axis=1),
                ),
                missing_out.sum(axis=1)
                / np.maximum(
                    1,
                    mf.sum(axis=1),
                ),
            ]
        )

    def _score_features(
        self,
        features: np.ndarray,
        median: np.ndarray,
        scale: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        z = np.maximum(
            0.0,
            (
                features
                - median[None, :]
            )
            / scale[None, :],
        )
        return (
            np.sqrt(
                np.mean(
                    z * z,
                    axis=1,
                )
            ),
            z,
        )

    def finalize_baseline(
        self,
    ) -> HealthyOperationalBaseline:
        if not self._healthy:
            raise ValueError(
                "at least one healthy run is required"
            )

        edge = np.vstack(
            [x.edge for x in self._healthy]
        )
        center = np.vstack(
            [x.center for x in self._healthy]
        )
        scale = np.vstack(
            [x.scale for x in self._healthy]
        )
        missing = np.vstack(
            [x.missing for x in self._healthy]
        )

        edge_low = self._q(
            edge,
            self.config.edge_lower_quantile,
        )
        edge_high = self._q(
            edge,
            self.config.edge_upper_quantile,
        )
        center_low = self._q(
            center,
            self.config.node_lower_quantile,
        )
        center_high = self._q(
            center,
            self.config.node_upper_quantile,
        )
        scale_low = self._q(
            scale,
            self.config.node_lower_quantile,
        )
        scale_high = self._q(
            scale,
            self.config.node_upper_quantile,
        )
        missing_high = self._q(
            missing,
            self.config.node_upper_quantile,
        )

        feature_blocks = [
            self._fractions(
                run,
                edge_low,
                edge_high,
                center_low,
                center_high,
                scale_low,
                scale_high,
                missing_high,
            )
            for run in self._healthy
        ]
        features = np.vstack(feature_blocks)

        median = np.nanmedian(
            features,
            axis=0,
        )
        mad = (
            1.4826
            * np.nanmedian(
                np.abs(
                    features
                    - median[None, :]
                ),
                axis=0,
            )
        )
        std = np.nanstd(
            features,
            axis=0,
        )

        resolution = np.asarray(
            [
                1
                / max(
                    1,
                    len(self._frozen),
                ),
                1
                / max(
                    1,
                    len(self._frozen),
                ),
                1
                / max(
                    1,
                    len(self._node_idx),
                ),
                1
                / max(
                    1,
                    len(self._node_idx),
                ),
                1
                / max(
                    1,
                    len(self._node_idx),
                ),
            ],
            dtype=float,
        )

        feature_scale = np.where(
            mad > 1e-12,
            mad,
            np.where(
                std > 1e-12,
                std,
                resolution,
            ),
        )

        score_blocks = [
            self._score_features(
                block,
                median,
                feature_scale,
            )[0]
            for block in feature_blocks
        ]
        scores = np.concatenate(score_blocks)

        window_threshold = float(
            np.quantile(
                scores,
                self.config.warning_quantile,
            )
        )

        persistence = max(
            1,
            self.config.persistence_windows,
        )
        confirmation_stats = []
        for run_scores in score_blocks:
            if len(run_scores) < persistence:
                continue
            width = (
                len(run_scores)
                - persistence
                + 1
            )
            stacked = np.vstack(
                [
                    run_scores[
                        offset : offset + width
                    ]
                    for offset in range(persistence)
                ]
            )
            confirmation_stats.append(
                np.min(
                    stacked,
                    axis=0,
                )
            )

        if confirmation_stats:
            threshold = float(
                np.quantile(
                    np.concatenate(
                        confirmation_stats
                    ),
                    self.config.confirmation_quantile,
                )
                + self.config.threshold_epsilon
            )
        else:
            threshold = (
                window_threshold
                + self.config.threshold_epsilon
            )

        stats = []
        for run, block, run_scores in zip(
            self._healthy,
            feature_blocks,
            score_blocks,
        ):
            above = (
                run_scores
                > threshold
            )

            confirmed = 0
            streak = 0
            in_episode = False

            for flag in above:
                streak = (
                    streak + 1
                    if flag
                    else 0
                )
                if (
                    streak
                    >= self.config.persistence_windows
                    and not in_episode
                ):
                    confirmed += 1
                    in_episode = True
                if not flag:
                    in_episode = False

            stats.append(
                {
                    "run_id": run.run_id,
                    "windows": int(
                        len(run_scores)
                    ),
                    "above_threshold_windows": int(
                        above.sum()
                    ),
                    "confirmed_episodes": confirmed,
                    "max_score": (
                        float(
                            run_scores.max()
                        )
                        if len(run_scores)
                        else None
                    ),
                    "column_coverage": run.coverage,
                }
            )

        self.baseline = HealthyOperationalBaseline(
            frozen_edges=len(self._frozen),
            backbone_groups=len(self._groups),
            node_groups=len(self._node_idx),
            edge_q_low=tuple(
                float(x)
                for x in edge_low
            ),
            edge_q_high=tuple(
                float(x)
                for x in edge_high
            ),
            node_center_q_low=tuple(
                float(x)
                for x in center_low
            ),
            node_center_q_high=tuple(
                float(x)
                for x in center_high
            ),
            node_scale_q_low=tuple(
                float(x)
                for x in scale_low
            ),
            node_scale_q_high=tuple(
                float(x)
                for x in scale_high
            ),
            node_missing_q_high=tuple(
                float(x)
                for x in missing_high
            ),
            feature_median=tuple(
                float(x)
                for x in median
            ),
            feature_scale=tuple(
                float(x)
                for x in feature_scale
            ),
            score_threshold=threshold,
            window_quantile_threshold=window_threshold,
            threshold_method=(
                "confirmation_statistic_quantile"
            ),
            confirmation_quantile=(
                self.config.confirmation_quantile
            ),
            healthy_windows=int(
                len(scores)
            ),
            healthy_run_stats=tuple(stats),
        )

        return self.baseline

    def _warning_outcome(
        self,
        score: float,
        streak: int,
        healthy_history_established: bool,
    ) -> Outcome:
        assert self.baseline is not None

        if (
            score
            <= self.baseline.score_threshold
        ):
            profile = Profile(
                state="warning-candidate",
                evidence=[],
                retired_reason=(
                    "score is inside the "
                    "healthy operational envelope"
                ),
            )
            return evaluate_profile(
                profile
            ).outcome

        evidence = [
            EvidenceItem(
                "score_exceeds",
                (
                    "structural drift score "
                    "exceeds healthy threshold"
                ),
                EvidenceStatus.MEASURED,
            )
        ]

        if (
            streak
            >= self.config.persistence_windows
        ):
            evidence.append(
                EvidenceItem(
                    "persistent",
                    (
                        "warning persists for "
                        "the configured "
                        "confirmation horizon"
                    ),
                    EvidenceStatus.MEASURED,
                )
            )

        if healthy_history_established:
            evidence.append(
                EvidenceItem(
                    "healthy_history",
                    (
                        "the run established a "
                        "healthy operational state "
                        "before departure"
                    ),
                    EvidenceStatus.MEASURED,
                )
            )
        else:
            evidence.append(
                EvidenceItem(
                    "startup_ood",
                    (
                        "the run began outside the "
                        "healthy operational envelope"
                    ),
                    EvidenceStatus.MEASURED,
                )
            )

        profile = Profile(
            state="warning-candidate",
            evidence=evidence,
            requires=(
                "score_exceeds",
                "persistent",
                "healthy_history",
            ),
            routers=[
                Router(
                    "await confirmation window",
                    "score_exceeds",
                    ("next_window",),
                    status=EvidenceStatus.MEASURED,
                ),
                Router(
                    "startup regime investigation",
                    "startup_ood",
                    ("unknown_startup_regime",),
                    status=EvidenceStatus.MEASURED,
                ),
            ],
        )
        return evaluate_profile(
            profile
        ).outcome

    def detect(
        self,
        values: np.ndarray,
        source_columns: Iterable[str],
        *,
        run_id: str,
    ) -> DetectionResult:
        if self.baseline is None:
            raise RuntimeError(
                "finalize_baseline() must be "
                "called before detect()"
            )

        measured = self._measure(
            values,
            source_columns,
            run_id,
        )
        baseline = self.baseline

        features = self._fractions(
            measured,
            np.asarray(
                baseline.edge_q_low
            ),
            np.asarray(
                baseline.edge_q_high
            ),
            np.asarray(
                baseline.node_center_q_low
            ),
            np.asarray(
                baseline.node_center_q_high
            ),
            np.asarray(
                baseline.node_scale_q_low
            ),
            np.asarray(
                baseline.node_scale_q_high
            ),
            np.asarray(
                baseline.node_missing_q_high
            ),
        )

        scores, z = self._score_features(
            features,
            np.asarray(
                baseline.feature_median
            ),
            np.asarray(
                baseline.feature_scale
            ),
        )
        above = (
            scores
            > baseline.score_threshold
        )

        windows = []
        streak = 0
        healthy_streak = 0
        healthy_history_established = False

        for i, (score, flag) in enumerate(
            zip(scores, above)
        ):
            if flag:
                streak += 1
                healthy_streak = 0
            else:
                streak = 0
                healthy_streak += 1
                if (
                    healthy_streak
                    >= self.config.healthy_history_windows
                ):
                    healthy_history_established = True

            outcome = self._warning_outcome(
                float(score),
                streak,
                healthy_history_established,
            )
            end = int(measured.ends[i])

            windows.append(
                WarningWindow(
                    window_index=i,
                    start_row=(
                        end
                        - self.config.window_size
                        + 1
                    ),
                    end_row=end,
                    score=float(score),
                    threshold=(
                        baseline.score_threshold
                    ),
                    above_threshold=bool(flag),
                    profiler_outcome=(
                        outcome.value
                    ),
                    features=tuple(
                        float(x)
                        for x in features[i]
                    ),
                    feature_z=tuple(
                        float(x)
                        for x in z[i]
                    ),
                )
            )

        episodes = []
        i = 0

        while i < len(above):
            if not above[i]:
                i += 1
                continue

            j = i
            while (
                j + 1 < len(above)
                and above[j + 1]
            ):
                j += 1

            if (
                j - i + 1
                >= self.config.persistence_windows
            ):
                confirm = (
                    i
                    + self.config.persistence_windows
                    - 1
                )
                prior = above[:i]
                if i == 0:
                    has_healthy_history = False
                else:
                    required = max(
                        1,
                        self.config.healthy_history_windows,
                    )
                    has_healthy_history = any(
                        np.all(
                            ~prior[
                                start : start + required
                            ]
                        )
                        for start in range(
                            max(
                                0,
                                len(prior)
                                - required
                                + 1,
                            )
                        )
                    )

                episodes.append(
                    WarningEpisode(
                        start_window=i,
                        end_window=j,
                        start_row=int(
                            measured.ends[i]
                        ),
                        end_row=int(
                            measured.ends[j]
                        ),
                        confirm_window=confirm,
                        confirm_row=int(
                            measured.ends[
                                confirm
                            ]
                        ),
                        max_score=float(
                            np.max(
                                scores[
                                    i : j + 1
                                ]
                            )
                        ),
                        classification=(
                            "confirmed_deterioration"
                            if has_healthy_history
                            else "startup_regime_mismatch"
                        ),
                    )
                )

            i = j + 1

        first_deterioration = next(
            (
                episode
                for episode in episodes
                if episode.classification
                == "confirmed_deterioration"
            ),
            None,
        )

        return DetectionResult(
            run_id=run_id,
            rows=measured.rows,
            column_coverage=(
                measured.coverage
            ),
            windows=tuple(windows),
            episodes=tuple(episodes),
            first_episode_start_window=(
                episodes[0].start_window
                if episodes
                else None
            ),
            first_confirm_window=(
                episodes[0].confirm_window
                if episodes
                else None
            ),
            first_deterioration_start_window=(
                first_deterioration.start_window
                if first_deterioration
                else None
            ),
            first_deterioration_confirm_window=(
                first_deterioration.confirm_window
                if first_deterioration
                else None
            ),
            baseline=baseline,
        )
