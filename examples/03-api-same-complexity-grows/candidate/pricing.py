def shipping_cost(weight: float, expedited: bool = False) -> float:
    if weight < 0:
        return 0.0
    if expedited:
        if weight > 10:
            return 25.0
        return 12.0
    if weight > 10:
        return 8.0
    return 2.0
