from typing import Protocol, Self, Type


class FactoryProtocol[T](Protocol):
    def _create(self, obj_type: Type[T]) -> T:
        """Create an instance of object type"""


class FactoryDescriptor[T]:
    """Descriptor creates and caches api/repo instances in api/repo/client sync/async classes"""

    def __init__(self, obj_type: Type[T]) -> None:
        self._obj_type = obj_type
        self._objects: dict[int, T] = {}

    def __get__(
        self,
        owner: FactoryProtocol[T] | None,
        owner_type: Type[FactoryProtocol[T]] | None = None,
    ) -> T | Self:
        if owner is None:
            return self

        # The descriptor can be used with several owner instances
        _id = id(owner)

        if _id not in self._objects:
            self._objects[_id] = owner._create(self._obj_type)  # noqa

        return self._objects[_id]
