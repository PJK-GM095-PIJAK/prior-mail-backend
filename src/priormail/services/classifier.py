"""Priority classifier service.

Loads the HuggingFace-hosted DistilBERT priority checkpoint and runs inference.
Wrapped behind the :class:`Classifier` protocol (ML_PIPELINE.md §6 /
BACKEND_INTEGRATION_GUIDE §5) so the implementation (HF, ONNX, …) is swappable
without touching call sites.

Loaded once at app startup; a load failure raises :class:`ModelUnavailableError`
so the app refuses to boot (fail loud — CLAUDE.md §7).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, cast, runtime_checkable

from pydantic import BaseModel

from priormail.core.errors import ModelUnavailableError
from priormail.core.logging import get_logger
from priormail.services.preprocess import build_priority_input

if TYPE_CHECKING:
    from transformers import PreTrainedModel, PreTrainedTokenizerBase

    from priormail.core.config import Settings

logger = get_logger(__name__)


class Prediction(BaseModel):
    """A single classification result."""

    label: str
    confidence: float


@runtime_checkable
class Classifier(Protocol):
    """Swappable classifier interface (ML_PIPELINE.md §6)."""

    version: str

    def predict(self, inputs: list[str]) -> list[Prediction]:
        """Classify a batch of pre-built input strings."""
        ...


class PriorityClassifier:
    """DistilBERT priority classifier backed by a local HF checkpoint directory."""

    def __init__(
        self,
        model: PreTrainedModel,
        tokenizer: PreTrainedTokenizerBase,
        version: str,
    ) -> None:
        self._model = model
        self._tokenizer = tokenizer
        self.version = version

    def predict(self, inputs: list[str]) -> list[Prediction]:
        """Classify a batch of pre-built ``{subject} [SEP] {body}`` strings.

        Tokenizes with truncation to 512 tokens, runs a single forward pass,
        and maps the argmax class via the model's ``id2label`` config.
        """
        import torch

        if not inputs:
            return []

        enc = self._tokenizer(
            inputs,
            truncation=True,
            max_length=512,
            padding=True,
            return_tensors="pt",
        )
        with torch.no_grad():
            logits = self._model(**enc).logits
        probs = logits.softmax(dim=-1)
        id2label = cast("dict[int, str]", self._model.config.id2label)

        predictions: list[Prediction] = []
        for row in probs:
            idx = int(row.argmax())
            predictions.append(
                Prediction(label=id2label[idx], confidence=float(row[idx]))
            )
        return predictions

    def classify(self, subject: str | None, body: str | None) -> Prediction:
        """Build the model input from raw subject/body and classify it."""
        text = build_priority_input(subject, body)
        return self.predict([text])[0]


def load_priority_classifier(settings: Settings) -> PriorityClassifier:
    """Download (if needed) and load the priority checkpoint from the HF Hub.

    Files live under a ``{version}/`` subfolder of the repo
    (BACKEND_INTEGRATION_GUIDE §2), so we snapshot just that subfolder and load
    from the local path. Any failure is re-raised as
    :class:`ModelUnavailableError` so the app refuses to start.
    """
    repo_id = settings.priority_model_repo_id
    version = settings.priority_model_version
    revision = settings.priority_model_revision

    logger.info(
        "loading_priority_model",
        repo_id=repo_id,
        version=version,
        revision=revision,
    )
    try:
        from huggingface_hub import snapshot_download
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        local_root = snapshot_download(
            repo_id,
            revision=revision,
            allow_patterns=f"{version}/*",
        )
        model_path = f"{local_root}/{version}"

        tokenizer = AutoTokenizer.from_pretrained(model_path)
        model = AutoModelForSequenceClassification.from_pretrained(model_path)
        model.eval()
    except Exception as exc:  # noqa: BLE001 — re-raised as a typed error below.
        raise ModelUnavailableError(
            f"Failed to load priority model {repo_id}/{version}: {exc}",
            details={"repo_id": repo_id, "version": version},
        ) from exc

    logger.info("priority_model_loaded", version=version)
    return PriorityClassifier(model=model, tokenizer=tokenizer, version=version)
