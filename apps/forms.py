from django import forms
from django.contrib.auth.models import User
from .models import UserProfile, User, CareerJourney, ActionPlan, Opportunity

class UserUpdateForm(forms.ModelForm):
    first_name = forms.CharField(max_length=30, required=False, widget=forms.TextInput(
        attrs={'class': 'form-control', 'placeholder': 'Enter your first name'}))
    last_name = forms.CharField(max_length=150, required=False, widget=forms.TextInput(
        attrs={'class': 'form-control', 'placeholder': 'Enter your last name'}))

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['avatar']
        widgets = {
            'avatar': forms.FileInput(attrs={'class': 'form-control'}),
        }

class WhatsAppSubscribeForm(forms.ModelForm):
    phone_number = forms.CharField(
        label="Your WhatsApp Number",
        help_text="Enter your number with the country code, e.g., +15551234567.",
        widget=forms.TextInput(attrs={'placeholder': '+15551234567'})
    )

    class Meta:
        model = UserProfile
        fields = ['phone_number']