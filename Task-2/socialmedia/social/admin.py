from django.contrib import admin
from .models import Post, PostImages, Comment, UserProfile, Notification, ThreadModel

# Register your models here.
class PostAdmin(admin.ModelAdmin):
    list_display = ['author', 'created_on', 'caption']

class CommentAdmin(admin.ModelAdmin):
    list_display = ['author', 'created_on', 'comment', 'post']

class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'name', 'bio', 'birth_date', 'location', 'picture', 'banner']


admin.site.register(Post, PostAdmin)
admin.site.register(Comment, CommentAdmin)
admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(Notification)
admin.site.register(ThreadModel)