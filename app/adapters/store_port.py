"""StorePort interface, MockStoreAdapter, and WooCommerceAdapter (ADR-0002, ADR-0003, ADR-0009)."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


class StoreError(Exception):
    """Raised when an error occurs during store API interaction."""


class StorePort(ABC):
    """Hexagonal Port interface for external e-commerce stores (WooCommerce)."""

    @abstractmethod
    def get_product_by_sku(self, sku: str) -> dict[str, Any] | None:
        """Lookup an existing product in store by SKU (idempotency key)."""

    @abstractmethod
    def get_all_products(self) -> list[dict[str, Any]]:
        """Retrieve all active products in the store."""

    @abstractmethod
    def batch_sync(
        self,
        create: list[dict[str, Any]],
        update: list[dict[str, Any]],
        delete: list[int] | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Perform batch create/update/delete conforming to WooCommerce REST v3 batch contract."""

    @abstractmethod
    def restore_product(self, woo_id: int, snapshot_data: dict[str, Any]) -> dict[str, Any]:
        """Restore product to a previous snapshot state."""

    @abstractmethod
    def delete_product(self, woo_id: int) -> bool:
        """Delete/trash product from the store (used in rollback of newly created products)."""


class MockStoreAdapter(StorePort):
    """In-memory mock store simulating WooCommerce REST v3 batch API idempotently by SKU."""

    def __init__(self) -> None:
        self._products: dict[int, dict[str, Any]] = {}
        self._next_id: int = 1001

    def clear(self) -> None:
        """Reset mock store state (useful for tests)."""
        self._products.clear()
        self._next_id = 1001

    def get_product_by_sku(self, sku: str) -> dict[str, Any] | None:
        """Lookup product by SKU in memory."""
        for prod in self._products.values():
            if str(prod.get("sku")).strip() == sku.strip():
                return dict(prod)
        return None

    def get_all_products(self) -> list[dict[str, Any]]:
        """Retrieve copy of all mock store products."""
        return [dict(p) for p in self._products.values()]

    def batch_sync(
        self,
        create: list[dict[str, Any]],
        update: list[dict[str, Any]],
        delete: list[int] | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Execute batch operation mimicking WooCommerce /products/batch."""
        created_items: list[dict[str, Any]] = []
        updated_items: list[dict[str, Any]] = []
        deleted_items: list[dict[str, Any]] = []

        # 1. Process creations
        for item in create:
            existing = self.get_product_by_sku(item.get("sku", ""))
            if existing:
                # Idempotent safeguard: if already exists, update instead
                existing.update(item)
                self._products[existing["id"]] = existing
                updated_items.append(dict(existing))
            else:
                new_id = self._next_id
                self._next_id += 1
                record = dict(item)
                record["id"] = new_id
                self._products[new_id] = record
                created_items.append(dict(record))

        # 2. Process updates
        for item in update:
            item_id = item.get("id")
            if item_id and item_id in self._products:
                self._products[item_id].update(item)
                updated_items.append(dict(self._products[item_id]))
            elif item.get("sku"):
                existing = self.get_product_by_sku(item["sku"])
                if existing:
                    existing.update(item)
                    self._products[existing["id"]] = existing
                    updated_items.append(dict(existing))

        # 3. Process deletions
        if delete:
            for d_id in delete:
                if d_id in self._products:
                    removed = self._products.pop(d_id)
                    deleted_items.append(removed)

        return {
            "create": created_items,
            "update": updated_items,
            "delete": deleted_items,
        }

    def restore_product(self, woo_id: int, snapshot_data: dict[str, Any]) -> dict[str, Any]:
        """Restore previous state."""
        record = dict(snapshot_data)
        record["id"] = woo_id
        self._products[woo_id] = record
        return dict(record)

    def delete_product(self, woo_id: int) -> bool:
        """Remove product from store."""
        if woo_id in self._products:
            del self._products[woo_id]
            return True
        return False


class WooCommerceAdapter(StorePort):
    """Real WooCommerce REST API v3 adapter using batch endpoint (ADR-0003)."""

    def __init__(
        self,
        base_url: str | None = None,
        consumer_key: str | None = None,
        consumer_secret: str | None = None,
    ) -> None:
        self.base_url = (base_url or settings.WOOCOMMERCE_URL).rstrip("/")
        self.consumer_key = consumer_key or settings.WOOCOMMERCE_CONSUMER_KEY
        self.consumer_secret = consumer_secret or settings.WOOCOMMERCE_CONSUMER_SECRET

    def _client(self) -> Any:
        import httpx

        return httpx.Client(
            base_url=self.base_url,
            auth=(self.consumer_key, self.consumer_secret),
            timeout=30.0,
        )

    def get_product_by_sku(self, sku: str) -> dict[str, Any] | None:
        """Query product by SKU."""
        with self._client() as client:
            resp = client.get("/wp-json/wc/v3/products", params={"sku": sku})
            if resp.is_success:
                items = resp.json()
                return items[0] if items else None
            return None

    def get_all_products(self) -> list[dict[str, Any]]:
        """Retrieve products list."""
        with self._client() as client:
            resp = client.get("/wp-json/wc/v3/products", params={"per_page": 100})
            if resp.is_success:
                return list(resp.json())
            return []

    def batch_sync(
        self,
        create: list[dict[str, Any]],
        update: list[dict[str, Any]],
        delete: list[int] | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Send batch payload to WooCommerce."""
        payload: dict[str, Any] = {"create": create, "update": update}
        if delete:
            payload["delete"] = delete

        with self._client() as client:
            resp = client.post("/wp-json/wc/v3/products/batch", json=payload)
            if not resp.is_success:
                raise StoreError(f"WooCommerce batch call failed: {resp.status_code} - {resp.text}")
            return dict(resp.json())

    def restore_product(self, woo_id: int, snapshot_data: dict[str, Any]) -> dict[str, Any]:
        """Restore product in WooCommerce."""
        with self._client() as client:
            resp = client.put(f"/wp-json/wc/v3/products/{woo_id}", json=snapshot_data)
            if not resp.is_success:
                raise StoreError(f"Restore failed: {resp.text}")
            return dict(resp.json())

    def delete_product(self, woo_id: int) -> bool:
        """Force delete product in WooCommerce."""
        with self._client() as client:
            resp = client.delete(f"/wp-json/wc/v3/products/{woo_id}", params={"force": True})
            return bool(resp.is_success)


# Global singleton instance for in-memory MockStore
_mock_store_instance = MockStoreAdapter()


def get_store_adapter() -> StorePort:
    """Factory providing configured StorePort adapter according to STORE_MODE."""
    if settings.STORE_MODE == "live":
        try:
            return WooCommerceAdapter()
        except Exception as e:
            logger.warning(
                "Failed to initialize live WooCommerce adapter (%s); using mock store.", e
            )

    return _mock_store_instance
