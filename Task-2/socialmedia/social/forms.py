from django import forms
from .models import Post, Comment, MessageModel

class PostForm(forms.ModelForm):
    caption = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': '3',
            'placeholder': 'Say something...'
        })
    )
    
    class Meta:
        model = Post
        fields = ['caption'] 

class CommentForm(forms.ModelForm):
    comment = forms.CharField(
        label = '',
        widget=forms.Textarea(attrs={
            'rows': '2',
            'placeholder': 'Add a comment...',
            'class': 'comment-input'
        })
    )
    
    class Meta:
        model = Comment
        fields = ['comment']

class DeactivateAccountForm(forms.Form):
    confirm_deactivate = forms.BooleanField(required=True, label="I confirm I want to deactivate my account")

class DeleteAccountForm(forms.Form):
    confirm_delete = forms.BooleanField(required=True, label="I confirm I want to permanently delete my account")

class ShareForm(forms.Form):
    caption = forms.CharField(
        label = '',
        widget = forms.Textarea(attrs={
            'rows' : 3,
            'placeholder' : 'Share something...',
            'class': 'comment-input'
        })
    )

class ThreadForm(forms.Form):
    username = forms.CharField(
        label = '',
        max_length = 100
    )

class MessageForm(forms.ModelForm):
    body = forms.CharField(label='', widget=forms.Textarea(attrs={'class': 'message-input'}))
    image = forms.ImageField(required=False)

    class Meta:
        model = MessageModel
        fields = ['body', 'image']