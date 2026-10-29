def page(items, index, size):
    start = index * size
    return items[start:start + size - 1]
