from django.shortcuts import render, redirect
from django.views import View
from .models import Post, PostImages, Comment, ThreadModel, UserProfile, Notification, MessageModel, Tag
from .forms import DeactivateAccountForm, DeleteAccountForm, PostForm, CommentForm, ShareForm, ThreadForm, MessageForm
from django.views.generic.edit import UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.http import HttpResponseRedirect, HttpResponse
from django.db.models import Q
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.contrib.auth.models import User

# Create your views here.
class PostListView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        logged_in_user = request.user

        # Get posts authored by users the logged-in user follows
        user_following_posts = Post.objects.filter(
            author__profile__followers__in=[logged_in_user.id]
        ).order_by('-created_on', '-shared_on')

        # Get posts shared by users the logged-in user follows (regardless of original author)
        shared_posts = Post.objects.filter(
            shared_user__profile__followers__in=[logged_in_user.id]
        ).order_by('-shared_on', '-created_on')

        # Combine the original posts and shared posts (without duplicates)
        posts = (user_following_posts | shared_posts).distinct().order_by('-created_on', '-shared_on')

        # Dictionaries to store follow status and visibility messages
        shared_user_following_status = {}
        author_following_status = {}
        visibility_message = {}

        comments_count = {}
        for post in posts:
            # Check if the logged-in user follows the shared user (for shared posts)
            if post.shared_user:
                is_following_shared_user = post.shared_user.profile.followers.filter(pk=logged_in_user.pk).exists()
                shared_user_following_status[post.id] = is_following_shared_user
            else:
                shared_user_following_status[post.id] = False

            # Check if the logged-in user follows the post's author
            is_following_author = post.author.profile.followers.filter(pk=logged_in_user.pk).exists()
            author_following_status[post.id] = is_following_author

            # New condition: if the post author is the logged-in user, allow visibility
            if post.author == logged_in_user:
                visibility_message[post.id] = None
            # Check if the author's profile is public or the logged-in user follows the author
            elif not post.author.profile.private or is_following_author:
                visibility_message[post.id] = None  # No visibility message, post is visible
            else:
                visibility_message[post.id] = "You cannot view this post because you do not follow the author. Follow them to see the content."

            comments_count[post.id] = Comment.objects.filter(post=post).count()

        share_form = ShareForm()

        context = {
            'post_list': posts,
            'comments_count': comments_count,
            'shareform': share_form,
            'shared_user_following_status': shared_user_following_status,
            'author_following_status': author_following_status,
            'visibility_message': visibility_message,  # Add visibility messages to context
        }

        return render(request, 'social/post_list.html', context)
    
class SharePostView(View):
    def post(self, request, pk, *args, **kwargs):
        original_post = Post.objects.get(pk=pk)
        form = ShareForm(request.POST)

        if form.is_valid():
            new_post = Post(
                shared_caption = self.request.POST.get('caption'),
                caption = original_post.caption,
                author = original_post.author,
                created_on = original_post.created_on,
                shared_user = request.user,
                shared_on = timezone.now(),
            )

            new_post.save()

            for img in original_post.image.all():
                new_post.image.add(img)

            new_post.save()

            notification = Notification.objects.create(
                notification_type = 4, 
                from_user = request.user,
                to_user = new_post.author,
                post = new_post
            )
        
        return redirect('post-list')
    
class PostDetailView(LoginRequiredMixin, View):
    def get(self, request, pk, *args, **kwargs):
        post = Post.objects.get(pk=pk)
        form = CommentForm()
        share_form = ShareForm()

        comments = Comment.objects.filter(post = post).order_by('-created_on')

        context = {
            'post' : post,
            'form' : form,
            'comments' : comments,
            'comment_count': comments.count(),
            'shareform': share_form,
        }

        return render(request, 'social/post-detail.html', context)
    def post(self, request, pk, *args, **kwargs):
        post = Post.objects.get(pk=pk)
        form = CommentForm(request.POST)
        share_form = ShareForm()

        if form.is_valid():
            new_comment = form.save(commit=False)
            new_comment.author = request.user
            new_comment.post = post
            new_comment.save()

            new_comment.create_tags()
        
        comments = Comment.objects.filter(post = post).order_by('-created_on')

        if request.user != post.author:
            notification = Notification.objects.create(
                notification_type = 2, 
                from_user = request.user,
                to_user = post.author,
                post = post
            )

        context = {
            'post' : post,
            'form' : form,
            'comments' : comments,
            'comment_count': comments.count(),
            'shareform': share_form,
        }

        return render(request, 'social/post-detail.html', context)
    
class ExploreView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        logged_in_user = request.user

        # Get the first 5 tags 
        tags = Tag.objects.all()[:5]

        # Get all profiles that are not followed by the current user
        profiles = UserProfile.objects.all().exclude(followers=logged_in_user)

        # Get public profiles that are not followed by the current user
        public_profiles = profiles.filter(private=False)

        # Get posts from public profiles not followed by the user
        user_not_following_posts = Post.objects.filter(
            author__profile__in=public_profiles
        ).exclude(author=logged_in_user).select_related('author', 'author__profile').order_by('-created_on')

        # Get shared posts by users who are not followed by the user
        shared_posts = Post.objects.filter(
            shared_user__profile__in=public_profiles
        ).exclude(shared_user=logged_in_user).select_related('shared_user', 'author', 'author__profile').order_by('-shared_on')

        # Combine original posts and shared posts
        all_posts = list(user_not_following_posts) + list(shared_posts)
        all_posts = sorted(all_posts, key=lambda post: post.shared_on or post.created_on, reverse=True)

        # Store follow status and visibility messages
        author_following_status = {}
        visibility_message = {}
        comments_count = {}

        for post in all_posts:
            # Check if the logged-in user follows the post's author
            is_following_author = post.author.profile.followers.filter(pk=logged_in_user.pk).exists()
            author_following_status[post.id] = is_following_author

            # Check visibility: user sees own posts, public profiles, or posts from followed users
            if post.author == logged_in_user:
                visibility_message[post.id] = None
            elif not post.author.profile.private or is_following_author:
                visibility_message[post.id] = None  # No visibility message, post is visible
            else:
                visibility_message[post.id] = "You cannot view this post because you do not follow the author. Follow them to see the content."

            # Count comments for each post
            comments_count[post.id] = Comment.objects.filter(post=post).count()

        # Prepare the share form
        share_form = ShareForm()

        # Context to render in the template
        context = {
            'tags' : tags,
            'profiles': profiles,
            'post_list': all_posts,
            'comments_count': comments_count,
            'shareform': share_form,
            'author_following_status': author_following_status,
            'visibility_message': visibility_message,
        }

        return render(request, 'social/explore.html', context)
    
class ProfileView(LoginRequiredMixin, View):
    def get(self, request, pk, *args, **kwargs):
        profile = UserProfile.objects.get(pk=pk)
        user = profile.user

        # Get posts authored by the profile owner
        original_posts = Post.objects.filter(
            author=user, shared_user__isnull=True
        ).order_by('-created_on')

        # Get posts shared by the user
        shared_posts = Post.objects.filter(
            shared_user=user
        ).order_by('-shared_on')

        # Prepare context data
        author_following_status = {}
        visibility_message = {}
        comments_count = {}

        for post in shared_posts:
            # Check if the logged-in user follows the post's author
            is_following_author = post.author.profile.followers.filter(pk=request.user.pk).exists()
            author_following_status[post.id] = is_following_author

            # Check visibility: user sees own posts, public profiles, or posts from followed users
            if post.author == request.user:
                visibility_message[post.id] = None
            elif not post.author.profile.private or is_following_author:
                visibility_message[post.id] = None  # No visibility message, post is visible
            else:
                visibility_message[post.id] = "You cannot view this post because you do not follow the author. Follow them to see the content."

        followers = profile.followers.all()
        number_of_followers = followers.count()
        following = profile.following.all()
        number_of_following = following.count()

        for post in original_posts:
            comments_count[post.id] = Comment.objects.filter(post=post).count()
        for post in shared_posts:
            comments_count[post.id] = Comment.objects.filter(post=post).count()

        context = {
            'user': user,
            'profile': profile,
            'original_posts': original_posts,
            'shared_posts': shared_posts,
            'posts_count': original_posts.count() + shared_posts.count(),
            'comments_count': comments_count,
            'number_of_followers': number_of_followers,
            'number_of_following': number_of_following,
            'is_following': request.user in followers,
            'author_following_status': author_following_status,
            'visibility_message': visibility_message,
        }

        return render(request, 'social/profile.html', context)
    
class ManagePostView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        # Retrieve posts authored by the current user
        posts = Post.objects.filter(author=request.user, shared_user__isnull=True).order_by('-created_on')

        # Prepare the context
        context = {
            'post_list': posts,
            'form': PostForm()
        }

        return render(request, 'social/manage-post.html', context)
    def post(self, request, *args, **kwargs):
        posts = Post.objects.filter(author=request.user, shared_user__isnull=True).order_by('-created_on')
        form = PostForm(request.POST)

        # Retrieve multiple images from the 'images' input field
        files = request.FILES.getlist('images')  

        if form.is_valid():
            new_post = form.save(commit=False)
            new_post.author = request.user
            new_post.save()  # Save the new post first to get an ID

            new_post.create_tags()

            # Loop through the uploaded files
            for f in files:
                # Create a PostImages instance for each file
                img_instance = PostImages(image=f)
                img_instance.save()  # Save the image instance to the database
                
                # Add the PostImages instance to the ManyToMany field of the Post
                new_post.image.add(img_instance)

            # After saving, prepare posts for rendering
            context = {
                'post_list': posts,
                'form': form
            }
            return render(request, 'social/manage-post.html', context)

        # If the form is not valid, render the same page with errors
        context = {
            'post_list': posts,
            'form': form
        }
        return render(request, 'social/manage-post.html', context)
    
class PostEditView(LoginRequiredMixin, UserPassesTestMixin, View):
    def get(self, request, *args, **kwargs):
        post = self.get_object()
        form = PostForm(instance=post)

        context = {
            'form': form,
            'post': post,
            'images': post.image.all()  # Get existing images for this post
        }
        return render(request, 'social/post-edit.html', context)
    def post(self, request, *args, **kwargs):
        post = self.get_object()
        form = PostForm(request.POST, instance=post)

        if form.is_valid():
            updated_post = form.save(commit=False)
            updated_post.author = request.user  # Maintain the author
            updated_post.save()  # Save the updated post

            # Handle image uploads
            existing_images = post.image.all()  # Retrieve existing images
            files = request.FILES.getlist('images')  # Get new uploaded images

            # Only delete images if there are new ones uploaded
            if files:
                for img in existing_images:
                    img.delete()  # Delete existing images if new ones are uploaded

                # Loop through uploaded files and save them
                for f in files:
                    img_instance = PostImages(image=f)
                    img_instance.save()  # Save the image instance to the database
                    
                    # Add the PostImages instance to the ManyToMany field of the Post
                    updated_post.image.add(img_instance)

            # If no new images were uploaded, existing ones remain intact

            return redirect('manage-post')  # Redirect after successfully updating

        # If the form is not valid, render the same page with errors
        context = {
            'form': form,
            'post': post,
            'images': existing_images  # Retain existing images to show in the form
        }
        return render(request, 'social/post-edit.html', context)

    def get_object(self):
        # Retrieve the post to edit
        post_id = self.kwargs.get('pk')  # Assuming the post ID is passed as a URL parameter
        return Post.objects.get(pk=post_id)

    def test_func(self):
        post = self.get_object()
        return self.request.user == post.author
    
class PostDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Post
    template_name = 'social/post-delete.html'
    success_url = reverse_lazy('manage-post')

    def test_func(self):
        post = self.get_object()
        return self.request.user == post.author

class CommentDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Comment
    template_name = 'social/comment-delete.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        comment = self.get_object()  
        context['post_pk'] = comment.post.pk  
        return context

    def get_success_url(self):
        comment = self.get_object()
        post_pk = comment.post.pk
        return reverse_lazy('post-detail', kwargs={'pk' : post_pk})
    
    def test_func(self):
        post = self.get_object()
        return self.request.user == post.author
    
class CommentEditView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Comment
    fields = ['comment']
    template_name = 'social/comment-edit.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        comment = self.get_object()  
        context['post_pk'] = comment.post.pk  
        return context

    def get_success_url(self):
        comment = self.get_object()
        post_pk = comment.post.pk
        return reverse_lazy('post-detail', kwargs={'pk' : post_pk})
    
    def test_func(self):
        post = self.get_object()
        return self.request.user == post.author
    
class EditProfileView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = UserProfile
    fields = ['name', 'bio', 'birth_date', 'location', 'picture', 'banner']
    template_name = 'social/edit-profile.html'

    def get_success_url(self):
        pk = self.kwargs['pk']
        return reverse_lazy('profile', kwargs={'pk': pk})
    
    def test_func(self):
        profile = self.get_object()
        return self.request.user == profile.user
    
class AddFollower(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        profile_to_follow = UserProfile.objects.get(pk=pk)
        current_user_profile = request.user.profile
        
        # Add the followed user to the current user's 'following' list
        current_user_profile.following.add(profile_to_follow.user)
        
        # Add the current user to the profile's 'followers' list
        profile_to_follow.followers.add(request.user)

        notification = Notification.objects.create(
            notification_type = 3, 
            from_user = request.user,
            to_user = profile_to_follow.user,
        )

        return redirect('profile', pk=profile_to_follow.pk)
    
class RemoveFollower(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        profile_to_unfollow = UserProfile.objects.get(pk=pk)
        current_user_profile = request.user.profile
        
        # Remove the unfollowed user from the current user's 'following' list
        current_user_profile.following.remove(profile_to_unfollow.user)
        
        # Remove the current user from the profile's 'followers' list
        profile_to_unfollow.followers.remove(request.user)

        return redirect('profile', pk=profile_to_unfollow.pk)
    
class AddFollowing(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        profile = UserProfile.objects.get(pk=pk)
        current_user_profile = request.user.profile
        current_user_profile.following.add(profile.user)
        return redirect('profile', pk=profile.pk)

class RemoveFollowing(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        profile = UserProfile.objects.get(pk=pk)
        current_user_profile = request.user.profile
        current_user_profile.following.remove(profile.user)
        return redirect('profile', pk=profile.pk)
    
class ToggleLike(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        post = Post.objects.get(pk=pk)

        if request.user in post.likes.all():
            post.likes.remove(request.user)  
        else:
            post.likes.add(request.user)
            if request.user != post.author:
                notification = Notification.objects.create(
                    notification_type = 1, 
                    from_user = request.user,
                    to_user = post.author,
                    post = post
                )

        next_url = request.POST.get('next', '/')
        return HttpResponseRedirect(next_url)
    
class UserSearch(View):
    def get(self, request, *args, **kwargs):
        query = self.request.GET.get('query')

        profile_list = UserProfile.objects.filter(
            Q(user__username__icontains=query)
        )

        tag = Tag.objects.filter(name=query).first()

        post_list = None
        author_following_status = {}
        visibility_message = {}
        comments_count = {}

        if tag:
            post_list = Post.objects.filter(
                Q(caption__icontains=query) | Q(shared_caption__icontains=query)
            )

            if post_list:
                for post in post_list:
                    # Check if the logged-in user follows the post's author
                    is_following_author = post.author.profile.followers.filter(pk=request.user.pk).exists()
                    author_following_status[post.id] = is_following_author

                    # Check visibility: user sees own posts, public profiles, or posts from followed users
                    if post.author == request.user:
                        visibility_message[post.id] = None
                    elif not post.author.profile.private or is_following_author:
                        visibility_message[post.id] = None  # No visibility message, post is visible
                    else:
                        visibility_message[post.id] = "You cannot view this post because you do not follow the author. Follow them to see the content."

                    # Count comments for each post
                    comments_count[post.id] = Comment.objects.filter(post=post).count()

        context = {
            'profile_list': profile_list,
            'post_list': post_list,
            'tag': tag,
            'visibility_message': visibility_message,  # Add this to context
            'author_following_status': author_following_status,
            'comments_count': comments_count,
        }

        return render(request, 'social/search.html', context)
    
class ListFollowers(View):
    def get(self, request, pk, *args, **kwargs):
        profile = UserProfile.objects.get(pk=pk)
        followers = profile.followers.all()

        context = {
            'profile' : profile,
            'followers' : followers,
        }

        return render(request, 'social/followers-list.html', context)
    
class ListFollowing(View):
    def get(self, request, pk, *args, **kwargs):
        profile = UserProfile.objects.get(pk=pk)
        followings = profile.following.all()

        context = {
            'profile' : profile,
            'followings' : followings,
        }

        return render(request, 'social/following-list.html', context)
    
class ToggleCommentLike(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        comment = Comment.objects.get(pk=pk)

        if request.user in comment.likes.all():
            comment.likes.remove(request.user)  
        else:
            comment.likes.add(request.user)
            if request.user != comment.author:
                notification = Notification.objects.create(
                    notification_type = 1, 
                    from_user = request.user,
                    to_user = comment.author,
                    comment = comment
                )  

        next_url = request.POST.get('next', '/')
        return HttpResponseRedirect(next_url)
    
class CommentReplyView(LoginRequiredMixin, View):
    def post(self, request, post_pk, pk, *args, **kwargs):
        post = Post.objects.get(pk=post_pk)
        parent_comment = Comment.objects.get(pk=pk)
        form = CommentForm(request.POST)

        if form.is_valid():
            new_comment = form.save(commit=False)
            new_comment.author = request.user
            new_comment.post = post
            new_comment.parent = parent_comment
            new_comment.save()

        # Only create a notification if the user replying is not the author of the original comment
        if request.user != parent_comment.author:
            notification = Notification.objects.create(
                notification_type = 2, 
                from_user = request.user,
                to_user = parent_comment.author,
                comment = new_comment
            )

        return redirect('post-detail', pk=post_pk)
    
class PostNotification(View):
    def get(self, request, notification_pk, post_pk, *args, **kwargs):
        notification = Notification.objects.get(pk=notification_pk)
        post = Post.objects.get(pk=post_pk)

        notification.user_has_seen = True
        notification.save()

        return redirect('post-detail', pk=post_pk)
    
class FollowNotification(View):
    def get(self, request, notification_pk, profile_pk, *args, **kwargs):
        notification = Notification.objects.get(pk=notification_pk)
        profile = UserProfile.objects.get(pk=profile_pk)

        notification.user_has_seen = True
        notification.save()

        return redirect('profile', pk=profile_pk)
    
class ThreadNotification(View):
    def get(self, request, notification_pk, thread_pk, *args, **kwargs):
        notification = Notification.objects.get(pk=notification_pk)
        thread = ThreadModel.objects.get(pk=thread_pk)

        notification.user_has_seen = True
        notification.save()

        return redirect('thread', pk=thread_pk)
    
class RemoveNotification(View):
    def delete(self, request, notification_pk, *args, **kwargs):
        notification = Notification.objects.get(pk=notification_pk)

        notification.user_has_seen = True
        notification.save()

        return HttpResponse('Success', content_type='text/plain')

class PostLikesView(View):
    def get(self, request, post_pk, *args, **kwargs):
        # Get the post by id
        post = Post.objects.get(pk=post_pk)
        
        # Get the users who liked this post
        liked_users = post.likes.all()

        context = { 
            'post' : post,
            'liked_users': liked_users
        }

        # Render the template and pass the liked users
        return render(request, 'social/post-likes.html', context)
    
class CommentLikesView(View):
    def get(self, request, post_pk, comment_pk, *args, **kwargs):
        # Get the post by id
        post = Post.objects.get(pk=post_pk)

        # Get the comment by id
        comment = Comment.objects.get(pk=comment_pk)
        
        # Get the users who liked this comment
        liked_users = comment.likes.all()

        context = { 
            'post' : post,
            'liked_users': liked_users
        }

        # Render the template and pass the liked users
        return render(request, 'social/comment-likes.html', context)
    
class SettingsView(View):
    def get(self, request, *args, **kwargs):
        profile = UserProfile.objects.get(user=request.user)
        
        context = {
            'profile': profile,
        }
        return render(request, 'social/settings.html', context)
    def post(self, request, *args, **kwargs):
        profile = UserProfile.objects.get(user=request.user)
        
        email = request.POST.get('email')
        phone_number = request.POST.get('phone')
        profile_visibility = request.POST.get('profileVisibility')
        message_privacy = request.POST.get('messagePrivacy')

        # Update user email
        if email and email != profile.user.email:
            profile.user.email = email
            profile.user.save()
        
        # Update phone number
        if phone_number != profile.phone_number:
            profile.phone_number = phone_number
            profile.save()

        # Update profile visibility
        if profile_visibility in ['public', 'private']:
            profile.private = (profile_visibility == 'private')
            profile.save()

        # Update who can send messages
        if message_privacy == 'everyone':
            profile.who_can_send_message = 1
        elif message_privacy == 'followers':
            profile.who_can_send_message = 2
        elif message_privacy == 'nobody':
            profile.who_can_send_message = 3
        profile.save()

        messages.success(request, 'Your account information has been updated successfully.')
        return redirect('settings')
    
@login_required
def deactivate_account(request):
    if request.method == 'POST':
        form = DeactivateAccountForm(request.POST)
        if form.is_valid():
            # Deactivate the account
            user_profile = request.user.profile
            user_profile.deactivated = True
            user_profile.save()

            # Log out the user and redirect to the landing page
            logout(request)
            return redirect('/')
    else:
        form = DeactivateAccountForm()
    
    return render(request, 'social/deactivate_account.html', {'form': form})

@login_required
def delete_account(request):
    if request.method == 'POST':
        form = DeleteAccountForm(request.POST)
        if form.is_valid():
            # Permanently delete the user account
            request.user.delete()

            # Log out the user (already deleted) and redirect to the landing page
            return redirect('/')
    else:
        form = DeleteAccountForm()
    
    return render(request, 'social/delete_account.html', {'form': form})

class ListThreads(View):
    def get(self, request, *args, **kwargs):
        threads = ThreadModel.objects.filter(Q(user=request.user) | Q(receiver=request.user))

        context = {
            'threads' : threads
        }

        return render(request, 'social/inbox.html', context)
    
class CreateThread(View):
    def get(self, request, *args, **kwargs):
        form = ThreadForm()

        context = {
            'form': form,
        }

        return render(request, 'social/create-thread.html', context)

    def post(self, request, *args, **kwargs):
        form = ThreadForm(request.POST)
        username = request.POST.get('username')

        try:
            # Retrieve the receiver user
            receiver = User.objects.get(username=username)
            receiver_profile = UserProfile.objects.get(user=receiver)

            # Check if a thread already exists
            if ThreadModel.objects.filter(user=request.user, receiver=receiver).exists():
                thread = ThreadModel.objects.filter(user=request.user, receiver=receiver)[0]
                return redirect('thread', pk=thread.pk)
            elif ThreadModel.objects.filter(user=receiver, receiver=request.user).exists():
                thread = ThreadModel.objects.filter(user=receiver, receiver=request.user)[0]
                return redirect('thread', pk=thread.pk)

            # Get the message permission of the receiver
            message_permission = receiver_profile.who_can_send_message

            # Check the receiver's message settings
            if message_permission == 1:
                # Everyone can message
                pass  # Do nothing, the user is allowed to send the message

            elif message_permission == 2:
                # Only followers can send messages
                if not receiver_profile.followers.filter(id=request.user.id).exists():
                    messages.error(request, "You must follow this user to send a message.")
                    return redirect('create-thread')

            elif message_permission == 3:
                # Nobody can send messages
                messages.error(request, "This user doesn't accept messages from anyone.")
                return redirect('create-thread')

            # If the form is valid and the user has permission to send a message
            if form.is_valid():
                thread = ThreadModel(
                    user=request.user,
                    receiver=receiver,
                )
                thread.save()
                return redirect('thread', pk=thread.pk)

        except User.DoesNotExist:
            messages.error(request, "Invalid Username")
            return redirect('create-thread')
        
class ThreadView(View):
    def get(self, request, pk, *args, **kwargs):
        form = MessageForm()
        thread = ThreadModel.objects.get(pk=pk)
        message_list = MessageModel.objects.filter(thread__pk__contains=pk)

        context = {
            'thread' : thread,
            'form' : form,
            'message_list' : message_list,
        }

        return render(request, 'social/thread.html', context)
    
class CreateMessage(View):
    def post(self, request, pk, *args, **kwargs):
        form = MessageForm(request.POST, request.FILES)
        thread = ThreadModel.objects.get(pk=pk)

        # Determine the receiver of the message
        if thread.receiver == request.user:
            receiver = thread.user
        else:
            receiver = thread.receiver

        receiver_profile = UserProfile.objects.get(user=receiver)

        # Get the message permission of the receiver
        message_permission = receiver_profile.who_can_send_message

        # Check if the current user is allowed to send a message
        if message_permission == 2:  # Only followers can send messages
            if not receiver_profile.followers.filter(id=request.user.id).exists():
                messages.error(request, "You must follow this user to send a message.")
                return redirect('inbox')  # Redirect to inbox with error

        elif message_permission == 3:  # Nobody can send messages
            messages.error(request, "This user doesn't accept messages from anyone.")
            return redirect('inbox')  # Redirect to inbox with error

        # If the user has permission and the form is valid, proceed to send the message
        if form.is_valid():
            message = form.save(commit=False)
            message.thread = thread
            message.sender_user = request.user
            message.receiver_user = receiver
            message.save()

            notification = Notification.objects.create(
                notification_type=4,
                from_user=request.user,
                to_user=receiver,
                thread=thread,
            )

        return redirect('thread', pk=pk)