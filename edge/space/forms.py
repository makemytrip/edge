from django import forms
from space.models import Space, Project, Env


class SpaceForm(forms.ModelForm):

    class Meta:
        model = Space
        fields = ['name', 'admin_dl', 'operator_dl', 'nav_color']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'admin_dl': forms.TextInput(attrs={'class': 'form-control'}),
            'operator_dl': forms.TextInput(attrs={'class': 'form-control'}),
            'nav_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'})
        }


class ProjectForm(forms.ModelForm):

    class Meta:
        model = Project
        fields = ['name', 'space', 'env', 'config']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'space': forms.Select(attrs={'class': 'form-control'}),
            'env': forms.Select(attrs={'class': 'form-control'}),
            'config': forms.Textarea(attrs={'class': "form-control"})
        }


class EnvForm(forms.ModelForm):

    class Meta:
        model = Env
        fields = ['name', 'script_file_name', 'config']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'script_file_name': forms.TextInput(attrs={'class': 'form-control'}),
            'config': forms.Textarea(attrs={'class': "form-control"})
        }
