from django.urls import path
from . import views, evidence_views, configuration_views, scoring_views, development_views, four_views, operational_views, vault_views
from .revised import views as revised_views
from .revised import live_views as dataset_views
from . import retired_views

app_name = 'ewaf'
urlpatterns = [
    path('policies/dataset/', retired_views.dataset_policy, name='dataset_policies'),
    path('policies/dataset/<int:policy_id>/', retired_views.dataset_policy, name='dataset_policy_review'),
    path('programs/<uuid:pk>/dataset-binding/', dataset_views.binding, name='dataset_binding'),
    path('dataset-inputs/<uuid:reference>/', retired_views.dataset_inputs, name='dataset_inputs'),
    path('revised/', operational_views.retired_preview, name='revised_preview'),
    path('revised/history/<int:run_id>/', revised_views.retained, name='revised_run'),
    path('revised/history/<int:run_id>/export/', revised_views.export, name='revised_export'),
    path('vault/', vault_views.vault, name='vault'),
    path('registered-inputs/<uuid:reference>/', vault_views.registered_review, name='registered_review'),
    path('', operational_views.programs, name='operational_programs'),
    path('programs/<uuid:pk>/', operational_views.workspace, name='operational_workspace'),
    path('programs/<uuid:pk>/selection-panel/', operational_views.selection_panel, name='selection_panel'),
    path('programs/<uuid:pk>/breakdown/', operational_views.breakdown, name='operational_breakdown'),
    path('programs/<uuid:pk>/calculation-guide/', retired_views.calculation_guide, name='operational_calculation_guide'),
    path('programs/<uuid:pk>/configuration/', operational_views.configuration, name='operational_configuration'),
    path('programs/<uuid:pk>/calculations/<int:run_id>/', operational_views.result, name='operational_run'),
    path('programs/<uuid:pk>/calculations/<int:run_id>/export/', operational_views.export_run, name='operational_export'),
    path('development/', development_views.laboratory, name='development_lab'),
    path('development/four/<uuid:pk>/', four_views.workspace, name='four_workspace'),
    path('development/program/<uuid:pk>/', development_views.development_program, name='development_program'),
    path('diagnostics/', scoring_views.scoring_list, name='scoring_list'),
    path('diagnostics/policy/<uuid:pk>/', scoring_views.scoring_policy, name='scoring_policy'),
    path('diagnostics/application/<uuid:reference>/', scoring_views.scoring_diagnostics, name='scoring_diagnostics'),
    path('diagnostics/application/<uuid:reference>/history/', scoring_views.scoring_history, name='scoring_history'),
    path('configurations/', configuration_views.configuration_list, name='configuration_list'),
    path('configurations/<uuid:pk>/', configuration_views.configuration_detail, name='configuration_detail'),
    path('configurations/<uuid:pk>/history/', configuration_views.configuration_history, name='configuration_history'),
    path('configurations/<uuid:pk>/policy-review/', configuration_views.policy_review, name='policy_review'),
    path('configurations/<uuid:pk>/<str:action>/', configuration_views.configuration_action, name='configuration_action'),
    path('evidence/', evidence_views.evidence_queue, name='evidence_queue'),
    path('evidence/policy/<uuid:pk>/', evidence_views.evidence_policy, name='evidence_policy'),
    path('evidence/<uuid:reference>/', evidence_views.evidence_readiness, name='evidence_readiness'),
    path('evidence/<uuid:reference>/history/', evidence_views.evidence_history, name='evidence_history'),
    path('evidence/<uuid:reference>/review/<str:criterion>/', evidence_views.evidence_review, name='evidence_review'),
    path('configuration/new/', views.configuration, name='configuration'),
    path('program/<uuid:pk>/', views.ranking, name='ranking'),
    path('application/<uuid:reference>/', views.assessment, name='assessment'),
]
