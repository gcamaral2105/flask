from flask import render_template
from app.main import main_bp

@main_bp.route('/', methods=['GET'])
def home():
    return render_template('main/home.html')