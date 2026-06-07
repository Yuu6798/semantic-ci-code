def shipping_cost(weight: float, expedited: bool = False) -> float:
    return 5.0 if expedited else 2.0
