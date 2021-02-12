from copy import copy

from tri_declarative import (
    declarative,
    EMPTY,
    flatten,
    getattr_path,
    Namespace,
    Refinable,
    setattr_path,
)
from tri_struct import Struct

from iommi.base import items


# def _get_type_of_namespace(dict_value):
#     if isinstance(dict_value, Namespace):
#         return type(dict_value)
#     else:
#         return Namespace


def prefixes(path):
    parts = [p for p in path.split('__') if p]
    for i in range(len(parts)):
        yield '__'.join(parts[: i + 1])


class RefinedNamespace(Namespace):
    __iommi_refined_description: str
    __iommi_refined_parent: Namespace
    __iommi_refined_delta: Namespace
    __iommi_refined_defaults: bool

    def __init__(self, description, parent, defaults=False, *args, **kwargs):
        delta = Namespace(*args, **kwargs)
        object.__setattr__(self, '__iommi_refined_description', description)
        object.__setattr__(self, '__iommi_refined_parent', parent)
        object.__setattr__(self, '__iommi_refined_delta', delta)
        object.__setattr__(self, '__iommi_refined_defaults', defaults)
        if defaults:
            default_updates = Namespace()
            updates = Namespace()
            for path, value in items(flatten(delta)):
                found = False
                missing = object()
                for prefix in prefixes(path):
                    existing = getattr_path(parent, prefix, missing)
                    if existing is missing:
                        break
                    if isinstance(existing, RefinableObject):
                        existing = existing.refine_defaults(**getattr_path(delta, prefix))
                        updates.setitem_path(prefix, existing)
                        found = True
                if not found:
                    default_updates.setitem_path(path, value)
            super().__init__(default_updates, parent, updates)
        else:
            updates = Namespace()
            for path, value in items(flatten(delta)):
                found = False
                missing = object()
                for prefix in prefixes(path):
                    existing = getattr_path(parent, prefix, missing)
                    if existing is missing:
                        break
                    if isinstance(existing, RefinableObject):
                        existing = existing.refine(**getattr_path(delta, prefix))
                        updates.setitem_path(prefix, existing)
                        found = True
                if not found:
                    updates.setitem_path(path, value)
            super().__init__(parent, updates)

    # def setitem_path(self, path, value):
    #     key, delimiter, rest_path = path.partition('__')
    #     existing = Struct.get(self, key)
    #
    #     if value is EMPTY:
    #         value = Namespace()
    #
    #     if delimiter:
    #         if isinstance(existing, RefinableObject):
    #             self[key] = existing.refine(**{rest_path: value})
    #         elif isinstance(existing, dict):
    #             type_of_namespace = _get_type_of_namespace(existing)
    #             self[key] = type_of_namespace(existing, {rest_path: value})
    #         elif callable(existing):
    #             self[key] = Namespace(dict(call_target=existing), {rest_path: value})
    #         else:
    #             # Unable to promote to Namespace, just overwrite
    #             self[key] = Namespace({rest_path: value})
    #     else:
    #         if existing is None:
    #             # This is a common case and checking for None is fast
    #             self[key] = value
    #         elif getattr(existing, 'shortcut', False):
    #             # Avoid merging Shortcuts
    #             self[key] = value
    #         elif isinstance(existing, RefinableObject):
    #             self[key] = existing.refine(**{rest_path: value})
    #         elif isinstance(existing, dict):
    #             type_of_namespace = _get_type_of_namespace(existing)
    #             if isinstance(value, dict):
    #                 self[key] = type_of_namespace(existing, value)
    #             elif callable(value):
    #                 self[key] = type_of_namespace(existing, call_target=value)
    #             else:
    #                 # Unable to promote to Namespace, just overwrite
    #                 self[key] = value
    #         elif callable(existing):
    #             if isinstance(value, dict):
    #                 type_of_namespace = _get_type_of_namespace(value)
    #                 self[key] = type_of_namespace(dict(call_target=existing), value)
    #             else:
    #                 self[key] = value
    #         else:
    #             self[key] = value

    def as_stack(self):
        refinements = []
        default_refinements = []
        node = self

        while isinstance(node, RefinedNamespace):
            try:
                description = object.__getattribute__(node, '__iommi_refined_description')
                parent = object.__getattribute__(node, '__iommi_refined_parent')
                delta = object.__getattribute__(node, '__iommi_refined_delta')
                defaults = object.__getattribute__(node, '__iommi_refined_defaults')
                value = (description, flatten(delta))
                if defaults:
                    default_refinements = default_refinements + [value]
                else:
                    refinements = [value] + refinements
                node = parent
            except AttributeError:
                break

        return default_refinements + [('base', flatten(node))] + refinements


# decorator
def refinable(f):
    f.refinable = True
    return f


def is_refinable_function(attr):
    return getattr(attr, 'refinable', False)


class EvaluatedRefinable(Refinable):
    pass


class RefinableMembers(Refinable):
    pass


def is_evaluated_refinable(x):
    return isinstance(x, EvaluatedRefinable) or getattr(x, '__iommi__evaluated', False)


@declarative(
    member_class=Refinable,
    parameter='refinable_members',
    is_member=is_refinable_function,
    add_init_kwargs=False,
)
class RefinableObject:

    namespace: Namespace
    is_refine_done: bool

    def __init__(self, namespace=None, **kwargs):
        if namespace is None:
            namespace = Namespace()
        else:
            namespace = Namespace(namespace)

        declared_items = self.get_declared('refinable_members')
        for name in list(kwargs):
            prefix, _, _ = name.partition('__')
            if prefix in declared_items:
                namespace.setitem_path(name, kwargs.pop(name))

        if kwargs:
            available_keys = '\n    '.join(sorted(declared_items.keys()))
            raise TypeError(
                f"""\
'{self.__class__.__name__}' object has no refinable attribute(s): {', '.join(f'"{k}"' for k in sorted(kwargs.keys()))}.
Available attributes:
    {available_keys}
"""
            )

        self.namespace = namespace
        self.is_refine_done = False

    def refine_done(self):
        assert not self.is_refine_done, f"refine_done() already invoked on {self}"

        declared_items = self.get_declared('refinable_members')
        remaining_namespace = Namespace(self.namespace)
        for k, v in items(declared_items):
            if isinstance(v, Refinable):
                setattr(self, k, remaining_namespace.pop(k, None))
            else:
                if k in remaining_namespace:
                    setattr(self, k, remaining_namespace.pop(k))

        if remaining_namespace:
            available_keys = '\n    '.join(sorted(declared_items.keys()))
            raise TypeError(
                f"""\
'{self.__class__.__name__}' object has no refinable attribute(s): {', '.join(f'"{k}"' for k in sorted(remaining_namespace.keys()))}.
Available attributes:
    {available_keys}
"""
            )
        self.is_refine_done = True

        self.on_refine_done()

        return self

    def on_refine_done(self):
        pass

    def refine(self, **args):
        assert not self.is_refine_done, f"{self} already finalized"
        result = copy(self)
        result.namespace = RefinedNamespace('refine', self.namespace, **args)
        return result

    def refine_defaults(self, **args):
        assert not self.is_refine_done, f"{self} already finalized"
        result = copy(self)
        result.namespace = RefinedNamespace('refine defaults', self.namespace, defaults=True, **args)
        return result

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.namespace}>"