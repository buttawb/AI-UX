from django.urls import path
from . import views

urlpatterns = [
    # For uploading design files (though we fetch Figma files directly)
    path('upload_design/', views.upload_design, name='upload_design'),


    # Fetch specific Figma file data based on selected file_id
    path('fetch_figma_file/', views.fetch_figma_file, name='fetch_figma_file'),

    # Generate heatmap data from OpenAI model based on selected Figma file
    path('generate_heatmap/', views.generate_heatmap, name='generate_heatmap'),
    path('fetch_figma_image_urls/', views.fetch_figma_image_urls, name='fetch_figma_image_url'),

    # New simulation routes
    path('simulation/', views.simulation_view, name='simulation_view'),
    path('generate_simulation/', views.generate_simulation, name='generate_simulation'),
]
