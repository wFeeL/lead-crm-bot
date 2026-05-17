from pathlib import Path
from typing import Any

import yaml

from app.schemas.content import (
    AppContentConfig,
    BrandConfig,
    CategoryConfig,
    ContentBundle,
    FaqEntry,
    TextsConfig,
)


class ContentService:
    """Loads and serves a content profile (brand, texts, faq, categories, config)."""

    def __init__(self, bundle: ContentBundle) -> None:
        self._bundle = bundle

    @property
    def bundle(self) -> ContentBundle:
        return self._bundle

    @property
    def brand(self) -> BrandConfig:
        return self._bundle.brand

    @property
    def texts(self) -> TextsConfig:
        return self._bundle.texts

    @property
    def faq(self) -> list[FaqEntry]:
        return self._bundle.faq

    @property
    def categories(self) -> list[CategoryConfig]:
        return self._bundle.categories

    @property
    def config(self) -> AppContentConfig:
        return self._bundle.config

    @classmethod
    def load(cls, profile_dir: Path) -> ContentBundle:
        """Load all YAML files from a profile directory and validate them."""
        brand_data = _read_yaml(profile_dir / "brand.yaml")
        texts_data = _read_yaml(profile_dir / "texts.yaml")
        faq_data = _read_yaml(profile_dir / "faq.yaml")
        categories_data = _read_yaml(profile_dir / "categories.yaml")
        config_data = _read_yaml(profile_dir / "config.yaml")

        return ContentBundle(
            brand=BrandConfig.model_validate(brand_data),
            texts=TextsConfig.model_validate(texts_data),
            faq=[FaqEntry.model_validate(item) for item in faq_data],
            categories=[CategoryConfig.model_validate(item) for item in categories_data],
            config=AppContentConfig.model_validate(config_data or {}),
        )


def _read_yaml(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Content file missing: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}
