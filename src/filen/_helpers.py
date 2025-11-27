from typing import Any, Protocol, Self, Type
from weakref import WeakKeyDictionary


class FactoryProtocol[T](Protocol):
    def _create(self, obj_type: Type[T], *args: Any, **kwargs: Any) -> T:
        """Create an instance of object type"""


class FactoryDescriptor[T]:
    """Descriptor creates and caches api/repo instances in api/repo/client sync/async classes"""

    def __init__(self, obj_type: Type[T], *args, **kwargs) -> None:
        self._obj_type = obj_type
        self._objects: WeakKeyDictionary[FactoryProtocol[T], T] = WeakKeyDictionary()
        self.args = args
        self.kwargs = kwargs

    def __get__(
        self,
        owner: FactoryProtocol[T] | None,
        owner_type: Type[FactoryProtocol[T]] | None = None,
    ) -> T | Self:
        if owner is None:
            return self

        if owner not in self._objects:
            self._objects[owner] = owner._create(self._obj_type, *self.args, **self.kwargs)  # noqa

        return self._objects[owner]
