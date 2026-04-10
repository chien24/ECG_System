from django.urls import path

from . import views

app_name = "ecg"

urlpatterns = [
    path("", views.home, name="home"),
    path("phan-tich-tin-hieu/", views.analyze_upload, name="analyze_upload"),
    path("lich-su-phan-tich/", views.analysis_history, name="analysis_history"),
    path(
        "xoa-lich-su-phan-tich/",
        views.delete_analysis_history,
        name="delete_history",
    ),
    path(
        "du-doan/<uuid:prediction_id>/",
        views.prediction_detail,
        name="prediction_detail",
    ),
    path(
        "tai-ve-csv/<uuid:prediction_id>/",
        views.download_ecg_csv,
        name="download_ecg_csv",
    ),
    path(
        "tai-ve-bieu-do/<uuid:prediction_id>/",
        views.download_ecg_chart,
        name="download_ecg_chart",
    ),
]


