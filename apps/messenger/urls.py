from django.urls import path

from . import views

app_name = 'messenger'

urlpatterns = [
    path('', views.ChatListView.as_view(), name='chat_list'),
    path('search/', views.MessageSearchView.as_view(), name='message_search'),
    path('upload/', views.FileUploadView.as_view(), name='file_upload'),
    path('<int:pk>/', views.ChatRoomView.as_view(), name='chat_room'),
    path('create/direct/<int:user_id>/', views.CreateDirectChatView.as_view(), name='create_direct'),
    path('create/group/', views.CreateGroupChatView.as_view(), name='create_group'),
]
