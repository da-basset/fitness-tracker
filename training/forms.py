from django import forms

from .models import Nutrient, Phase, Plan, Supplement, Workout


class WorkoutForm(forms.ModelForm):
    class Meta:
        model = Workout
        fields = ["name", "sub", "flavor", "color"]
        widgets = {
            "color": forms.RadioSelect,
            "name": forms.TextInput(attrs={"maxlength": 100}),
            "sub": forms.TextInput(attrs={"maxlength": 150, "placeholder": "e.g. Chest, Shoulders, Triceps"}),
            "flavor": forms.TextInput(attrs={"maxlength": 250, "placeholder": "Optional progression tip shown on the page"}),
        }


class PhaseForm(forms.ModelForm):
    class Meta:
        model = Phase
        fields = ["title", "order", "note"]
        widgets = {
            "title": forms.TextInput(attrs={"maxlength": 60, "placeholder": 'e.g. "Ramp-In", "Build", "Deload"'}),
            "order": forms.NumberInput(attrs={"min": 1}),
            "note": forms.Textarea(attrs={"rows": 3}),
        }


class PlanForm(forms.ModelForm):
    """Creates or renames a plan-library template. Only name/description --
    a plan's Workouts/Phases are built separately via the plan manager."""

    class Meta:
        model = Plan
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"maxlength": 150, "placeholder": "e.g. Beginner Strength"}),
            "description": forms.Textarea(attrs={"rows": 3, "placeholder": "Optional -- shown to the trainer only"}),
        }


class NutrientForm(forms.ModelForm):
    class Meta:
        model = Nutrient
        fields = ["name", "amount", "timing", "notes", "order"]
        widgets = {
            "name": forms.TextInput(attrs={"maxlength": 150, "placeholder": "e.g. Protein"}),
            "amount": forms.TextInput(attrs={"maxlength": 100, "placeholder": "e.g. 180g/day"}),
            "timing": forms.TextInput(attrs={"maxlength": 100, "placeholder": "e.g. Spread across meals"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
            "order": forms.NumberInput(attrs={"min": 1}),
        }


class SupplementForm(forms.ModelForm):
    class Meta:
        model = Supplement
        fields = ["name", "amount", "timing", "notes", "order"]
        widgets = {
            "name": forms.TextInput(attrs={"maxlength": 150, "placeholder": "e.g. Creatine"}),
            "amount": forms.TextInput(attrs={"maxlength": 100, "placeholder": "e.g. 5g"}),
            "timing": forms.TextInput(attrs={"maxlength": 100, "placeholder": "e.g. Morning"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
            "order": forms.NumberInput(attrs={"min": 1}),
        }
