from extensions import db


class Entry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(20), nullable=False)  # ISO date
    meal = db.Column(db.String(20), nullable=False)
    food_estimate = db.Column(db.String(200))
    calories = db.Column(db.Integer)
    notes = db.Column(db.Text)
    image_filename = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def __repr__(self):
        return f"<Entry {self.date} {self.meal} {self.calories}>"
