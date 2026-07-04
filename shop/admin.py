from django.contrib import admin

from .models import OwnedItem, ShopItem


@admin.register(ShopItem)
class ShopItemAdmin(admin.ModelAdmin):
    list_display = ('icon', 'name', 'category', 'price')
    list_filter = ('category',)
    search_fields = ('name',)


admin.site.register(OwnedItem)
