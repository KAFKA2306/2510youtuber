"""Workflow step abstraction for YouTube video generation pipeline."""

from .artifacts import ArtifactRetentionPolicy, DefaultArtifactRetentionPolicy, GeneratedArtifact
from .base import StepResult, WorkflowContext, WorkflowStep
from .failure import FailureBus, WorkflowFailureEvent
from .ports import NewsCollectionPort, SyncNewsCollectionAdapter
from .steps import (
    AlignSubtitlesStep,
    CollectNewsStep,
    GenerateMetadataStep,
    GenerateScriptStep,
    GenerateThumbnailStep,
    GenerateVideoStep,
    GenerateVisualDesignStep,
    QualityAssuranceStep,
    ReviewVideoStep,
    SynthesizeAudioStep,
    TranscribeAudioStep,
    UploadToDriveStep,
    UploadToYouTubeStep,
)

__all__ = [
    "WorkflowContext",
    "WorkflowStep",
    "StepResult",
    "GeneratedArtifact",
    "ArtifactRetentionPolicy",
    "DefaultArtifactRetentionPolicy",
    "FailureBus",
    "WorkflowFailureEvent",
    "NewsCollectionPort",
    "SyncNewsCollectionAdapter",
    "CollectNewsStep",
    "GenerateScriptStep",
    "GenerateVisualDesignStep",
    "SynthesizeAudioStep",
    "TranscribeAudioStep",
    "AlignSubtitlesStep",
    "GenerateVideoStep",
    "QualityAssuranceStep",
    "GenerateMetadataStep",
    "GenerateThumbnailStep",
    "UploadToDriveStep",
    "UploadToYouTubeStep",
    "ReviewVideoStep",
]
