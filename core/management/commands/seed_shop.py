from django.core.management.base import BaseCommand

from core.models import ShopItem

CATALOG = [
    # Food (consumable): restores satiety, small happiness bump.
    dict(name='Kibble',        category=ShopItem.FOOD, price=8,  icon='🥣',
         satiety_boost=20, happiness_boost=2, sort=1,
         description='Everyday crunchies. Cheap and cheerful.'),
    dict(name='Tuna Can',      category=ShopItem.FOOD, price=15, icon='🐟',
         satiety_boost=40, happiness_boost=6, sort=2,
         description='A fishy feast that fills the belly.'),
    dict(name='Cat Treats',    category=ShopItem.FOOD, price=12, icon='🍬',
         satiety_boost=12, happiness_boost=12, sort=3,
         description='Not filling, but oh so exciting.'),
    dict(name='Gourmet Salmon', category=ShopItem.FOOD, price=30, icon='🍣',
         satiety_boost=60, happiness_boost=14, sort=4,
         description='Restaurant quality. Purrs guaranteed.'),

    # Toys (permanent): play to boost happiness.
    dict(name='Yarn Ball',     category=ShopItem.TOY, price=25, icon='🧶',
         happiness_boost=10, sort=1, description='A timeless classic.'),
    dict(name='Feather Wand',  category=ShopItem.TOY, price=40, icon='🪶',
         happiness_boost=18, sort=2, description='Irresistible to any feline.'),
    dict(name='Laser Pointer', category=ShopItem.TOY, price=60, icon='🔴',
         happiness_boost=25, sort=3, description='The eternal, uncatchable dot.'),

    # Accessories (permanent, cosmetic): equip to dress the cat up.
    dict(name='Bow Tie',       category=ShopItem.ACCESSORY, price=35, icon='🎀', sort=1,
         description='Dapper and refined.'),
    dict(name='Party Hat',     category=ShopItem.ACCESSORY, price=45, icon='🎉', sort=2,
         description='Every day is a celebration.'),
    dict(name='Crown',         category=ShopItem.ACCESSORY, price=120, icon='👑', sort=3,
         description='For the true ruler of the household.'),
    dict(name='Cool Shades',   category=ShopItem.ACCESSORY, price=50, icon='🕶️', sort=4,
         description='Too cool for treats. (Still wants treats.)'),
]


class Command(BaseCommand):
    help = 'Populate the shop with the default catalog (idempotent).'

    def handle(self, *args, **options):
        created = 0
        for data in CATALOG:
            _, made = ShopItem.objects.update_or_create(
                name=data['name'], defaults=data
            )
            created += int(made)
        self.stdout.write(self.style.SUCCESS(
            f'Shop seeded: {len(CATALOG)} items ({created} new).'
        ))
