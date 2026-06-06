from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import json
import asyncio
from qa_engine import run_single_test, TEST_SCENARIOS, suggest_functionalities
from threading import Thread

app = Flask(__name__)
CORS(app)

# Configuración
REPORT_DIR = "Reportes"
os.makedirs(REPORT_DIR, exist_ok=True)

def run_async_test_in_thread(test_id, title, module, result_dict):
    try:
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        filepath = loop.run_until_complete(run_single_test(test_id, title, module))
        loop.close()
        result_dict["success"] = True
        result_dict["filepath"] = filepath
    except Exception as e:
        result_dict["success"] = False
        result_dict["error"] = str(e)

@app.route('/')
def index():
    # Obtener lista de reportes generados y sus detalles
    reports = []
    db_data = {}
    if os.path.exists('db.json'):
        with open('db.json', 'r', encoding='utf-8') as f:
            db_data = json.load(f)
            
    for f in os.listdir(REPORT_DIR):
        if f.endswith('.docx'):
            # Extraer TC-001 de Reporte_TC-001.docx
            test_id = f.replace('Reporte_', '').replace('.docx', '')
            details = db_data.get(test_id, {"title": "Desconocido", "module": "Desconocido"})
            reports.append({"filename": f, "test_id": test_id, "title": details["title"], "module": details["module"]})
            
    return render_template('index.html', scenarios=TEST_SCENARIOS, reports=reports)

@app.route('/generate', methods=['POST'])
def generate_test():
    data = request.json
    test_id = data.get('id', f"TC-NEW-{len(os.listdir(REPORT_DIR))+1}")
    title = data.get('title')
    module = data.get('module')
    
    if not title or not module:
        return jsonify({"success": False, "error": "Faltan datos"}), 400
        
    # Guardar en db.json
    db_data = {}
    if os.path.exists('db.json'):
        with open('db.json', 'r', encoding='utf-8') as f:
            db_data = json.load(f)
            
    db_data[test_id] = {"title": title, "module": module}
    with open('db.json', 'w', encoding='utf-8') as f:
        json.dump(db_data, f, ensure_ascii=False, indent=2)
        
    result = {}
    # Run async function in a separate thread so it doesn't block Flask or mess with loops
    thread = Thread(target=run_async_test_in_thread, args=(test_id, title, module, result))
    thread.start()
    thread.join() # Wait for completion (for simple use case)
    
    if result.get("success"):
        return jsonify({"success": True, "message": "Reporte generado con éxito", "filepath": result.get("filepath")})
    else:
        return jsonify({"success": False, "error": result.get("error", "Error desconocido")}), 500

@app.route('/recommend', methods=['POST'])
def recommend():
    data = request.json
    module = data.get('module')
    if not module:
        return jsonify({"success": False, "error": "Módulo requerido"})
        
    suggestions = suggest_functionalities(module)
    return jsonify({"success": True, "suggestions": suggestions})

@app.route('/reports/<path:filename>')
def download_report(filename):
    return send_from_directory(REPORT_DIR, filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
