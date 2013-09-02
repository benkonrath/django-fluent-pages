"""
Translation support for admin forms.
"""
import urllib
from django import forms
from django.conf import settings
from django.contrib import admin
from django.core.urlresolvers import reverse
from django.utils.encoding import iri_to_uri
from django.utils.translation import get_language
from fluent_pages.utils.i18n import normalize_language_code


def get_model_form_field(model, name, **kwargs):
    return model._meta.get_field_by_name(name)[0].formfield(**kwargs)


def get_language_name(language_code):
    try:
        return next(title for code, title in settings.LANGUAGES if code == language_code)
    except StopIteration:
        return language_code


class TranslatableModelFormMixin(object):
    """
    Form mixin, to fetch+store translated fields.
    """
    _translatable_model = None
    _translatable_fields = ()
    language_code = None   # Set by get_form()


    def __init__(self, *args, **kwargs):
        super(TranslatableModelFormMixin, self).__init__(*args, **kwargs)

        # Load the initial values for the translated fields
        instance = kwargs.get('instance', None)
        if instance:
            translation = instance._get_translated_model(auto_create=True)
            for field in self._translatable_fields:
                self.initial.setdefault(field, getattr(translation, field))


    def save(self, commit=True):
        self.instance.set_current_language(self.language_code)
        # Assign translated fields to the model (using the TranslatedAttribute descriptor)
        for field in self._translatable_fields:
            setattr(self.instance, field, self.cleaned_data[field])

        return super(TranslatableModelFormMixin, self).save(commit)



class TranslatableAdmin(admin.ModelAdmin):
    """
    Base class for translated admins
    """
    # Code partially taken from django-hvad

    class Media:
        css = {
            'all': ('fluent_pages/admin/language_tabs.css',)
        }

    query_language_key = 'language'

    def _language(self, request):
        return normalize_language_code(request.GET.get(self.query_language_key, get_language()))

    def get_object(self, request, object_id):
        """
        Make sure the object is fetched in the correct language.
        """
        object = super(TranslatableAdmin, self).get_object(request, object_id)
        if object is not None:
            object.set_current_language(self._language(request), initialize=True)

        return object

    def get_form(self, request, obj=None, **kwargs):
        form_class = super(TranslatableAdmin, self).get_form(request, obj, **kwargs)
        form_class.language_code = self._language(request)
        return form_class

    def get_available_languages(self, obj):
        if obj:
            return obj.get_available_languages()
        else:
            return []

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        lang_code = self._language(request)
        lang = get_language_name(lang_code)
        available_languages = self.get_available_languages(obj)
        context['title'] = '%s (%s)' % (context['title'], lang)
        context['current_is_translated'] = lang_code in available_languages
        context['allow_deletion'] = len(available_languages) > 1
        context['language_tabs'] = self.get_language_tabs(request, available_languages)
        #context['base_template'] = self.get_change_form_base_template()
        return super(TranslatableAdmin, self).render_change_form(request, context, add, change, form_url, obj)

    def get_language_tabs(self, request, available_languages):
        tabs = []
        get = request.GET.copy()  # QueryDict object
        language = self._language(request)
        tab_languages = []

        base_url = '{0}://{1}{2}'.format(request.is_secure() and 'https' or 'http', request.get_host(), request.path)

        for key, name in settings.LANGUAGES:
            get['language'] = key
            url = '{0}?{1}'.format(base_url, get.urlencode())

            if key == language:
                status = 'current'
            elif key in available_languages:
                status = 'available'
            else:
                status = 'empty'

            tabs.append((url, name, key, status))
            tab_languages.append(key)

        # Additional stale translations in the database?
        for key in available_languages:
            if key not in tab_languages:
                get['language'] = key
                url = '{0}?{1}'.format(base_url, get.urlencode())
                tabs.append((url, key, key, 'available'))

        return tabs
