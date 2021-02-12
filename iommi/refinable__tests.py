from typing import Dict

import pytest
from tri_declarative import (
    dispatch,
    Namespace,
    with_meta,
)

from iommi.refinable import (
    prefixes,
    Refinable,
    RefinableMembers,
    RefinableObject,
    RefinedNamespace,
)


def test_empty():
    class MyRefinableObject(RefinableObject):
        def __init__(self, a, x=None, **kwargs):
            self.a = a
            self.x = x
            super().__init__(**kwargs)

    my_refinable = MyRefinableObject(17, x=42)
    assert my_refinable.a == 17
    assert my_refinable.x == 42
    assert my_refinable.namespace == Namespace()


def test_refinable():
    class MyRefinableObject(RefinableObject):
        def __init__(self, a, x=None, **kwargs):
            self.a = a
            self.x = x
            super().__init__(**kwargs)

        b = Refinable()

    my_refinable = MyRefinableObject(17, x=42, b=4711)
    assert my_refinable.a == 17
    assert my_refinable.x == 42
    assert my_refinable.namespace == Namespace(b=4711)


def test_with_meta():
    @with_meta
    class MyRefinableObject(RefinableObject):
        a = Refinable()
        b = Refinable()

        class Meta:
            a = 1

    my_refinable = MyRefinableObject(b=2)
    assert my_refinable.namespace == Namespace(a=1, b=2)


def test_with_dispatch():
    class MyRefinableObject(RefinableObject):
        a = Refinable()
        b = Refinable()

        @dispatch(a=1)
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

    my_refinable = MyRefinableObject(b=2)
    assert my_refinable.namespace == Namespace(a=1, b=2)


def test_refine():
    class MyRefinableObject(RefinableObject):
        a = Refinable()

    my_refinable = MyRefinableObject(a=17)
    assert my_refinable.namespace == Namespace(a=17)

    my_refined_namespacey = my_refinable.refine(a=42)
    assert my_refined_namespacey.namespace == Namespace(a=42)
    assert isinstance(my_refined_namespacey, MyRefinableObject)


@pytest.mark.parametrize(
    'path, result',
    [
        ('', []),
        ('foo', ['foo']),
        ('foo__bar', ['foo', 'foo__bar']),
    ],
)
def test_prefixes(path, result):
    assert list(prefixes(path)) == result


class Fruit(RefinableObject):
    taste: str = Refinable()
    color: str = Refinable()


class Basket(RefinableObject):
    fruits: Dict[str, Fruit] = RefinableMembers()


def test_refine_recursive():

    basket = Basket(fruits__banana=Fruit(color='yellow'))
    basket = basket.refine(fruits__banana__taste='good')
    basket.refine_done()
    basket.fruits.banana.refine_done()

    assert basket.fruits.banana.taste == 'good'
    assert basket.fruits.banana.color == 'yellow'
    assert (
        str(basket.namespace.as_stack()) == "["
        "('base', {'fruits__banana': <Fruit Namespace(color=yellow)>}), "
        "('refine', {'fruits__banana__taste': 'good'})"
        "]"
    )


def test_refine_recursive_defaults():
    basket = Basket(fruits__banana=Fruit(color='yellow'))
    basket = basket.refine_defaults(
        fruits__banana__color='blue',
        fruits__banana__taste='good',
    )
    basket.refine_done()
    basket.fruits.banana.refine_done()

    assert basket.fruits.banana.taste == 'good'
    assert basket.fruits.banana.color == 'yellow'
    assert (
        str(basket.namespace.as_stack()) == "["
        "('refine defaults', {'fruits__banana__color': 'blue', 'fruits__banana__taste': 'good'}), "
        "('base', {'fruits__banana': <Fruit Namespace(color=yellow)>})"
        "]"
    )


def test_refine_defaults():
    class MyRefinableObject(RefinableObject):
        a = Refinable()

    my_refined_refinable = MyRefinableObject().refine_defaults(a=42)
    assert my_refined_refinable.namespace == Namespace(a=42)

    my_refinable = MyRefinableObject(a=17)
    assert my_refinable.namespace == Namespace(a=17)

    my_refined_refinable = my_refinable.refine_defaults(a=42)
    assert my_refined_refinable.namespace == Namespace(a=17)


def test_done_refine():
    class MyRefinableObject(RefinableObject):
        a = Refinable()

    my_namespacey = MyRefinableObject(a=42)
    my_namespacey.refine_done()

    assert my_namespacey.a == 42


def test_no_double_done_refine():
    with pytest.raises(AssertionError) as e:
        RefinableObject().refine_done().refine_done()
    assert 'refine_done() already invoked on' in str(e.value)


def test_refined_namespace():
    base = Namespace(a=1, b=2)
    refined = RefinedNamespace('refinement', base, b=3)
    assert refined == Namespace(a=1, b=3)


def test_refined_defaults():
    base = Namespace(a=1, b=2)
    refined = RefinedNamespace('refinement', base, defaults=True, b=3, c=4)
    assert refined == Namespace(a=1, b=2, c=4)


def test_refined_as_stack():
    namespace = Namespace(a=1)
    namespace = RefinedNamespace('refinement', namespace, b=2)
    namespace = RefinedNamespace('defaults refinement', namespace, defaults=True, c=3)
    namespace = RefinedNamespace('further refinement', namespace, d=4)
    namespace = RefinedNamespace('further defaults refinement', namespace, defaults=True, e=5)
    assert namespace == dict(a=1, b=2, c=3, d=4, e=5)
    assert namespace.as_stack() == [
        ('further defaults refinement', {'e': 5}),
        ('defaults refinement', {'c': 3}),
        ('base', {'a': 1}),
        ('refinement', {'b': 2}),
        ('further refinement', {'d': 4}),
    ]