from django.urls import path
from . import views
from . import simulation_helpers
from . import design_iteration
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.landing_page, name='landing_page'),
    path('upload_design/', views.upload_design, name='upload_design'),
    path('fetch_figma_file/', views.fetch_figma_file, name='fetch_figma_file'),
    path('generate_heatmap/', views.generate_heatmap, name='generate_heatmap'),
    path('fetch_figma_image_urls/', views.fetch_figma_image_urls, name='fetch_figma_image_url'),
    path('simulation/', simulation_helpers.simulation, name='simulation'),
    path('generate_simulation/', simulation_helpers.generate_simulation, name='generate_simulation'),
    path('design_iteration/', design_iteration.design_iteration_view, name='design_iteration'),
    path('generate_iteration/', design_iteration.generate_iteration, name='generate_iteration'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
