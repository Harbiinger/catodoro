from django.contrib.auth import login
from django.shortcuts import redirect, render

from cats.models import Cat

from .forms import RegisterForm
from .models import Player


def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            # bootstrap this player's world (cat still needs configuring)
            Player.for_user(user)
            Cat.for_user(user)
            login(request, user)
            return redirect('setup')
    else:
        form = RegisterForm()
    return render(request, 'registration/register.html', {'form': form})
