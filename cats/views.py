from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.templatetags.static import static

from core.models import Player

from .forms import CatSetupForm
from .models import CAT_COLORS, Cat


@login_required
def setup(request):
    """Onboarding / cat settings: choose the cat's name and colour."""
    player = Player.for_user(request.user)
    cat = Cat.for_user(request.user)
    first_time = not cat.configured
    if request.method == 'POST':
        form = CatSetupForm(request.POST, instance=cat)
        if form.is_valid():
            cat = form.save(commit=False)
            cat.configured = True
            cat.save()
            messages.success(request, f'{cat.name} is settled in. Welcome!')
            return redirect('dashboard')
    else:
        form = CatSetupForm(instance=cat)
    # content-pose image URL per colour that has an image set (a "cat model");
    # colours absent from this map fall back to the drawn SVG in the preview.
    model_images = {
        color: static(f'cats/{color}/{color}_content.png')
        for color in Cat.IMAGE_COLORS
    }
    return render(request, 'cats/setup.html', {
        'form': form, 'cat': cat, 'player': player,
        'colors': CAT_COLORS, 'first_time': first_time,
        'model_images': model_images,
    })
