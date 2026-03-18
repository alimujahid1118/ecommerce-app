from django.db import models
from django.utils.text import slugify
from django.urls import reverse

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(max_length=500, blank=True)
    image = models.ImageField(upload_to='photos/categories', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name_plural = "Category"

    def save(self, *args, **kwargs):
        if not self.slug:  # Only generate if empty
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_url(self):
        return reverse('products_by_category', args=[self.slug])