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

    def text(self, key: str, **kwargs: object) -> str:
        """Look up a text template by dotted path and apply str.format() with kwargs.

        Falls back to KeyError when the path does not resolve and TypeError when
        the resolved value is not a string template.
        """
        node: object = self._bundle.texts.model_dump()
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                raise KeyError(key)
            node = node[part]
        if not isinstance(node, str):
            raise TypeError(f"text key {key!r} resolves to non-string {type(node).__name__}")
        return node.format(**kwargs) if kwargs else node

    @staticmethod
    def load(profile_dir: Path) -> ContentBundle:
        """Load all YAML files from a profile directory and validate them."""
        brand_data = _read_yaml(profile_dir / "brand.yaml")
        texts_data = _read_yaml(profile_dir / "texts.yaml")
        faq_data = _read_yaml(profile_dir / "faq.yaml")
        categories_data = _read_yaml(profile_dir / "categories.yaml")
        config_data = _read_yaml(profile_dir / "config.yaml")

        return ContentBundle(
            brand=BrandConfig.model_validate(brand_data),
            texts=TextsConfig.model_validate(texts_data),
            faq=[FaqEntry.model_validate(item) for item in (faq_data or [])],
            categories=[CategoryConfig.model_validate(item) for item in (categories_data or [])],
            config=AppContentConfig.model_validate(config_data or {}),
        )


def _read_yaml(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Content file missing: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)
