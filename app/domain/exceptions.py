"""Domain exceptions for CatalogPilot."""


class DomainError(Exception):
    """Base domain error for CatalogPilot."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class EntityNotFoundError(DomainError):
    """Raised when a requested entity does not exist."""


class ProductNotFoundError(EntityNotFoundError):
    """Raised when a product is not found by ID or SKU."""


class CategoryNotFoundError(EntityNotFoundError):
    """Raised when a category is not found."""


class AttributeDefNotFoundError(EntityNotFoundError):
    """Raised when an attribute definition is not found."""


class DuplicateSKUError(DomainError):
    """Raised when attempting to create or update a product with an existing SKU."""


class DuplicateAttributeNameError(DomainError):
    """Raised when an attribute definition name already exists."""


class InvalidAttributeValueError(DomainError):
    """Raised when a product attribute value does not match allowed values."""


class ParentCategoryCycleError(DomainError):
    """Raised when a category hierarchy creates a cycle."""
