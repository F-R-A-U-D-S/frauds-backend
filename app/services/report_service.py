import os

from fastapi.responses import FileResponse

def get_report(report_id: int):
    #TO DO : Downloads dummy file currently
    file_path = os.path.join(os.path.dirname(__file__), "test_csv.csv")
    return FileResponse(file_path, media_type="text/csv", filename="test_csv.csv") 