def outer(x):
    def inner(y):
        if y:
            return 1
        return 2
    return inner(x)


class K:
    def m(self, x):
        return x

    class Inner:
        def deep(self, x):
            if x:
                return 1
            return 2


def outer(x):
    return 1 if x else 2
