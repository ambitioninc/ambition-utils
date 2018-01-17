from copy import deepcopy

from django.core.exceptions import ValidationError
from django.db.transaction import atomic
from django.forms.utils import ErrorDict


class NestedFormMixinBase(object):
    # nested_form_classes = []
    nested_form_configs = []

    def __init__(self, *args, **kwargs):
        super(NestedFormMixinBase, self).__init__(*args, **kwargs)

        self.nested_forms = []

        # Keep track of form prefixes to guarantee multiple of the same form are properly prefixed
        form_prefixes = {}

        for nested_form_config in self.nested_form_configs:
            form_kwargs = deepcopy(kwargs)
            prefix = nested_form_config.get('field_prefix')

            # Check if this form class already exists
            if nested_form_config['class'] in form_prefixes:
                # Make sure both have a prefix value
                if not form_prefixes[nested_form_config['class']] or not nested_form_config.get('field_prefix'):
                    raise ValidationError(
                        'Form {0} must have a field prefix'.format(nested_form_config['class'].__name__)
                    )

            # Set the prefix value to the form config prefix
            form_prefixes[nested_form_config['class']] = nested_form_config.get('field_prefix')

            if form_kwargs.get('data') and prefix:
                for prefixed_key, value in form_kwargs['data'].items():
                    to_replace = '{0}_'.format(prefix)
                    if prefixed_key.startswith(to_replace):
                        key = prefixed_key.replace(to_replace, '')
                        form_kwargs['data'][key] = value
                        form_kwargs['data'].pop(prefixed_key)

            self.nested_forms.append({
                'instance': nested_form_config['class'](*args, **form_kwargs),
                'config': nested_form_config
            })

    def get_pre_save_method_kwargs(self):  # pragma: no cover
        return {}

    def get_post_save_method_kwargs(self, **kwargs):  # pragma: no cover
        return kwargs

    def get_required_forms(self):
        return [nested_form for nested_form in self.nested_forms if self.form_is_required(nested_form)]

    @atomic
    def save(self, *args, **kwargs):
        return super(NestedFormMixinBase, self).save(*args, **kwargs)

    def save_form(self, **kwargs):
        return None

    def form_is_required(self, nested_form):
        if nested_form['config'].get('required'):
            return True

        # Get the required flag value
        return self.cleaned_data.get(nested_form['config'].get('required_key'))

    def full_clean(self):
        """
        Cleans all of self.data and populates self._errors and
        self.cleaned_data.

        This is copied from django with an addition at the bottom
        """
        # This is the django code
        self._errors = ErrorDict()
        if not self.is_bound:  # pragma: no cover
            return
        self.cleaned_data = {}
        if self.empty_permitted and not self.has_changed():  # pragma: no cover
            return

        self._clean_fields()
        self._clean_form()
        self._post_clean()

        # This is the additional code that updates the form's errors with the nested form's errors
        required_forms = self.get_required_forms()
        for form in required_forms:
            self._errors.update(form['instance'].errors)


class NestedFormMixin(NestedFormMixinBase):
    @atomic
    def save(self, *args, **kwargs):
        form_kwargs = self.get_pre_save_method_kwargs()

        required_forms = self.get_required_forms()

        for form in required_forms:
            if form['config'].get('pre'):
                form_kwargs[form['config']['key']] = form['instance'].save(**form_kwargs)

        form_kwargs['form_save'] = self.save_form(**form_kwargs)
        form_kwargs = self.get_post_save_method_kwargs(**form_kwargs)

        for form in required_forms:
            if form['config'].get('post'):
                form_kwargs[form['config']['key']] = form['instance'].save(**form_kwargs)

        return form_kwargs['form_save']


class NestedModelFormMixin(NestedFormMixinBase):

    @atomic
    def save(self, commit=True):
        form_kwargs = self.get_pre_save_method_kwargs()

        required_forms = self.get_required_forms()

        for form in required_forms:
            if form['config'].get('pre'):
                form_kwargs[form['config']['key']] = form['instance'].save(**form_kwargs)

        form_kwargs['instance'] = super(NestedModelFormMixin, self).save(commit=commit)
        form_kwargs = self.get_post_save_method_kwargs(**form_kwargs)

        for form in required_forms:
            if form['config'].get('post'):
                form_kwargs[form['config']['key']] = form['instance'].save(**form_kwargs)

        return form_kwargs['instance']
