from copy import deepcopy

from django.core.exceptions import ValidationError
from django.db.transaction import atomic
from django.forms.utils import ErrorDict


class NestedFormConfig(object):
    """
    Defines how a nested form is handled in the context of another form. Any form class using a subclass of
    NestedFormMixinBase can define a nested_form_configs list with instances of NestedFormConfig
    """

    def __init__(self, cls, key, required=False, field_prefix=None, required_key=None, pre=False, post=False):
        """
        Sets all default values
        :param cls: Any form class reference
        :param key: The dict key that will be used when passing around form arguments during processing.
        The value of this dict will be the return value of the save method
        :type key: str
        :param required: Determines if this form's fields are always required
        :type required: bool
        :param field_prefix: Optional field for when multiple instance of the same form are nested. This allows
        the submitted data to have a prefix before each form field name.
        :type field_prefix: str
        :param required_key: Optional form field that causes the form to be required based on its presence.
        :type required_key: bool
        :param pre: Flag to indicate that the nested form should be processed before the parent form save method. This
        allows the nested form's save value to be available in the save method arguments keyed off of the key param.
        :type pre: bool
        :param post: Flag to indicate that the nested form should be processed after the parent form save method. This
        allows the parent form's save value to be available in the post save method arguments.
        :type post: bool
        """
        self.cls = cls
        self.key = key
        self.required = required
        self.field_prefix = field_prefix
        self.required_key = required_key
        self.pre = pre
        self.post = post
        self.instance = None

        assert self.cls
        assert self.key

    def set_instance(self, *args, **kwargs):
        self.instance = self.cls(*args, **kwargs)


class NestedFormMixinBase(object):
    """
    Allows a form to contain multiple and optional nested forms. The form configurations are defined in
    nested_form_configs and is defined by instances of NestedFormConfig
    """
    nested_form_configs = []

    def __init__(self, *args, **kwargs):
        super(NestedFormMixinBase, self).__init__(*args, **kwargs)

        # Build a list of all nest form configs
        self.nested_forms = []

        # Keep track of form prefixes to guarantee multiple of the same form are properly prefixed
        form_prefixes = {}

        for nested_form_config in self.nested_form_configs:
            # Deep copy the form kwargs to pass to each form instance
            form_kwargs = deepcopy(kwargs)
            prefix = nested_form_config.field_prefix

            # Check if this form class already exists
            if nested_form_config.cls in form_prefixes:
                # Make sure both have a prefix value
                if not form_prefixes[nested_form_config.cls] or not nested_form_config.field_prefix:
                    raise ValidationError(
                        'Form {0} must have a field prefix'.format(nested_form_config.cls.__name__)
                    )

            # Set the prefix value to the form config prefix
            form_prefixes[nested_form_config.cls] = nested_form_config.field_prefix

            # Process the form field keys when there is a prefix defined on the nested form
            if form_kwargs.get('data') and prefix:
                for prefixed_key, value in deepcopy(form_kwargs['data']).items():
                    # Check if the prefix is there to replace
                    to_replace = '{0}_'.format(prefix)
                    if prefixed_key.startswith(to_replace):
                        # Replace the prefix
                        key = prefixed_key.replace(to_replace, '')
                        form_kwargs['data'][key] = value

                        # Get rid of the prefixed key
                        form_kwargs['data'].pop(prefixed_key)

            # Create the form instance and pass the form data
            nested_form_config.set_instance(*args, **form_kwargs)

            # Add the form config to the list of nested form configs
            self.nested_forms.append(nested_form_config)

    def get_pre_save_method_kwargs(self):  # pragma: no cover
        """
        Optionally return a dict of data that will be passed through the chain of save methods with
        pre-forms, parent form, and post-forms
        """
        return {}

    def get_post_save_method_kwargs(self, **kwargs):  # pragma: no cover
        """
        Optionally return a dict of data that will be passed to the post-forms. All previous form data will be
        available here including pre-save data and parent form save data.
        """
        return kwargs

    def get_required_forms(self):
        """
        Checks which forms are required based on the params and returns a list of only the required forms
        :rtype: list of NestedFormConfig
        """
        return [nested_form for nested_form in self.nested_forms if self.form_is_required(nested_form)]

    def save_form(self, **kwargs):
        """
        Hook for the parent form to save an object so that it doesn't override the mixin's save method and logic.
        """
        return None

    def form_is_required(self, nested_form):
        """
        Handles the logic to check if an individual form is required
        """
        if nested_form.required:
            return True

        # Get the required flag value
        return self.cleaned_data.get(nested_form.required_key)

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
            self._errors.update(form.instance.errors)


class NestedFormMixin(NestedFormMixinBase):
    @atomic
    def save(self, *args, **kwargs):
        """
        Handles getting additional arguments, calling save on pre-save forms, calling save_form on the parent form,
        and calling save on post-save forms. The form kwargs are passed through the whole chain and the parent
        form's save_form return value is returned from this method.
        """
        # Get any additional arguments that should be passed to the save methods
        form_kwargs = self.get_pre_save_method_kwargs()

        # Get all required nested forms
        required_forms = self.get_required_forms()

        # Save all pre-save forms
        for form in required_forms:
            if form.pre:
                # Store the return value keyed off the form.key property
                form_kwargs[form.key] = form.instance.save(**form_kwargs)

        # Save the parent form
        form_kwargs['form_save'] = self.save_form(**form_kwargs)

        # Get any additional post-save arguments
        form_kwargs = self.get_post_save_method_kwargs(**form_kwargs)

        # Save all post-save forms
        for form in required_forms:
            if form.post:
                # Store the return value keyed off the form.key property
                form_kwargs[form.key] = form.instance.save(**form_kwargs)

        # Return the value from the parent form's save_form method
        return form_kwargs['form_save']


class NestedModelFormMixin(NestedFormMixinBase):

    @atomic
    def save(self, commit=True):
        """
        Handles getting additional arguments, calling save on pre-save forms, calling save on the parent model form,
        and calling save on post-save forms. The form kwargs are passed through the whole chain and the parent
        form's save return value is returned from this method.
        """
        # Get any additional arguments that should be passed to the save methods
        form_kwargs = self.get_pre_save_method_kwargs()

        # Get all required nested forms
        required_forms = self.get_required_forms()

        # Save all pre-save forms
        for form in required_forms:
            if form.pre:
                # Store the return value keyed off the form.key property
                form_kwargs[form.key] = form.instance.save(**form_kwargs)

        # Save the parent form
        form_kwargs['instance'] = super(NestedModelFormMixin, self).save(commit=commit)

        # Get any additional post-save arguments
        form_kwargs = self.get_post_save_method_kwargs(**form_kwargs)

        # Save all post-save forms
        for form in required_forms:
            if form.post:
                # Store the return value keyed off the form.key property
                form_kwargs[form.key] = form.instance.save(**form_kwargs)

        # Return the value from the parent form's save method
        return form_kwargs['instance']
