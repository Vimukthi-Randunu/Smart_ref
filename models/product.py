class Product:
    def __init__(self, name, category, quantity, reorder_level, sales_count=0):
        self.name = name
        self.category = category
        self.quantity = quantity
        self.reorder_level = reorder_level
        self.sales_count = sales_count

    def needs_refill(self):
        return self.quantity < self.reorder_level
    