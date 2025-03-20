from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=True)  # جعل كلمة المرور اختيارية للمستخدمين الاجتماعيين
    name = db.Column(db.String(100), nullable=True)
    avatar = db.Column(db.String(200), nullable=True)
    social_id = db.Column(db.String(100), nullable=True)  # معرف المستخدم في الخدمة الاجتماعية
    social_provider = db.Column(db.String(20), nullable=True)  # نوع الخدمة (google, facebook, apple)
    predictions = db.relationship('Prediction', backref='user', lazy=True)
    notifications = db.relationship('Notification', backref='user', lazy=True)  # ✅ إضافة العلاقة مع الإشعارات

class Prediction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    prediction = db.Column(db.String(100), nullable=False)
    confidence = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, server_default=db.func.now())

class Notification(db.Model):  # ✅ إضافة نموذج Notification
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, server_default=db.func.now())

    def __repr__(self):
        return f'<Notification {self.id} - {self.message}>'
