from .models import Category

def category_links(request):
    category_link = Category.objects.all()
    return dict(category_link=category_link)