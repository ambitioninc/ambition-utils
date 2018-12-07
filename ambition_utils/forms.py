import wrapt

from copy import deepcopy
from django import forms

from django.core.exceptions import ValidationError
from django.db import transaction


class NestedFormConfig(object):
    """
    Defines how a nested form is handled in the context of another form. Any form class using a subclass of
    NestedFormMixinBase can define a nested_form_configs list with instances of NestedFormConfig
    """

    def __init__(
        self,
        cls,
        key,
        required=False,
        field_prefix=None,
        required_key=None,
        pre=False,
        post=False,
        error_messages=None
    ):
        """
        Sets all default values

        :param cls: Any form class reference

        :param key: The dict key that will be used when passing around form arguments during processing.
                    The value of this dict will be the return value of the save method
        :type key: str

        :param required: Determines if this form's fields are always required
        :type required: bool

        :param field_prefix: Optional field for when multiple instance of the same form are nested.
                             This allows the submitted data to have a prefix before each form field name.
        :type field_prefix: str

        :param required_key: Optional form field that causes the form to be required based on its presence.
        :type required_key: str or None

        :param pre: Flag to indicate that the nested form should be processed before the parent form save method.
                    This allows the nested form's save value to be available in the save method
                    arguments keyed off of the key param.
        :type pre: bool

        :param post: Flag to indicate that the nested form should be processed after the parent form save method.
                    This allows the parent form's save value to be available in the post save method arguments.
        :type post: bool

        :param error_messages: Any error messages to override. This should be a multi dict with the top
                               level being the field name and its value being a dictionary of error_type => message
        :type error_messages: dict
        """

        # Store all the properties onto the class
        self.cls = cls
        self.key = key
        self.required = required
        self.field_prefix = field_prefix
        self.required_key = required_key
        self.pre = pre
        self.post = post
        self.error_messages = error_messages or {}
        self.instance = None

        # Assert that we have a class and key objects
        assert self.cls
        assert self.key

    def set_instance(self, base_form, *args, **kwargs):
        """
        Set the instance of the created form
        """

        # Create the instance with the passed arguments
        self.instance = self.cls(*args, **kwargs)

        # Add the base form as an attribute onto the nested form
        setattr(self.instance, 'nested_form_parent', base_form)

        # Apply any custom error messages
        for field_name, messages in self.error_messages.items():
            if field_name in self.instance.fields:
                self.instance.fields[field_name].error_messages.update(messages)


class NestedFormMixin(object):
    """
    Allows a form to contain multiple and optional nested forms. The form configurations are defined in
    nested_form_configs and is defined by instances of NestedFormConfig
    """

    # A list of nested form config items that should be nested within the main form
    nested_form_configs = []

    def __init__(self, *args, **kwargs):
        # Call the parent
        super(NestedFormMixin, self).__init__(*args, **kwargs)

        # Assert that we have a save method
        if not hasattr(self, 'save'):
            raise Exception('Base form must have a save method')

        # Wrap the save method around the nested form save
        self.save = self._nested_save(self.save)

        # Build a list of all nest form configs
        self.nested_forms = []

        # Keep track of form prefixes to guarantee multiple of the same form are properly prefixed
        form_prefixes = {}
        for nested_form_config in self.nested_form_configs:
            # Check if this form class already exists
            if nested_form_config.cls in form_prefixes:
                # Make sure both have a prefix value
                if not form_prefixes[nested_form_config.cls] or not nested_form_config.field_prefix:
                    raise ValidationError(
                        'Form {0} must have a field prefix'.format(nested_form_config.cls.__name__)
                    )

            # Create a link field on the main form
            # Check if a field already exists
            if nested_form_config.key in self.fields:
                raise Exception('A nested field with key {0} already exists on the base form'.format(
                    nested_form_config.key
                ))

            # Add the field to the base form so we can add errors and data for cleaning
            self.fields[nested_form_config.key] = forms.Field(required=False)

            # Build the nested form args, kwargs to init the nested form with
            nested_form_args = []
            nested_form_kwargs = {
                'data': {}
            }

            # Get the prefix
            prefix = nested_form_config.field_prefix

            # Set the prefix value to the form config prefix
            form_prefixes[nested_form_config.cls] = nested_form_config.field_prefix

            # Process the form field keys when there is a prefix defined on the nested form
            for key, value in deepcopy(self.data).items():
                # Check if the prefix is there to replace
                to_replace = '{0}_'.format(prefix)
                if key.startswith(to_replace):
                    # Update the key
                    key = key.replace(to_replace, '')

                # Apply the value to the data dict
                nested_form_kwargs['data'][key] = value

            # Get the nested form config init arguments
            nested_form_args, nested_form_kwargs = self.get_nested_form_init_args(
                nested_form_config=nested_form_config,
                args=nested_form_args,
                kwargs=nested_form_kwargs,
                base_form_args=args,
                base_form_kwargs=kwargs
            )

            # Create the form instance and pass the form data
            nested_form_config.set_instance(*nested_form_args, **nested_form_kwargs)

            # Add the form config to the list of nested form configs
            self.nested_forms.append(nested_form_config)

    @wrapt.decorator
    @transaction.atomic
    def _nested_save(self, wrapped, instance, args, kwargs):
        """
        This is a wrapper around the base forms save method.
        Handles getting additional arguments, calling save on pre-save forms, calling save_form on the parent form,
        and calling save on post-save forms. The form kwargs are passed through the whole chain and the parent
        form's save_form return value is returned from this method.

        :param wrapped: The original method
        :param instance: The instance the method is attached to
        :param args:
        :param kwargs:
        :return:
        """

        # Get all required nested forms
        required_forms = self.get_required_forms()

        # Keep track of the form responses
        responses = {}

        # Save all pre-save forms and apply the results to the base form kwargs and nested form kwargs
        for form in required_forms:
            if form.pre:
                # Get the args and kwargs for the nested form
                nested_form_args, nested_form_kwargs = self.get_nested_form_save_args(
                    nested_form_config=form,
                    args=[],
                    kwargs={},
                    base_form_args=args,
                    base_form_kwargs=kwargs
                )

                # Call the save method of the nested form
                response = form.instance.save(*nested_form_args, **nested_form_kwargs)

                # Store the response
                responses[form.key] = response

        # Save the parent form and store the result under the save key
        responses['save'] = wrapped(*args, **kwargs, **responses)

        # Save all post-save forms
        for form in required_forms:
            if form.post:
                # Get the args and kwargs for the nested form
                nested_form_args, nested_form_kwargs = self.get_nested_form_save_args(
                    nested_form_config=form,
                    args=[],
                    kwargs={},
                    base_form_args=args,
                    base_form_kwargs=kwargs
                )

                # Call the save method of the nested form
                # We assume all post save forms to assume they are nested
                response = form.instance.save(*nested_form_args, **nested_form_kwargs, **responses)

                # Store the response
                responses[form.key] = response

        # Call the save nested method
        self.save_nested(responses['save'], **responses)

        # Return the value from the parent form's save method
        return responses['save']

    def save_nested(self, response, **kwargs):
        """
        Called after all nested forms and the main form have been saved
        :param response: The response from the main form
        :param kwargs: The nested kwargs
        """
        pass

    def get_nested_form_init_args(self, nested_form_config, args, kwargs, base_form_args, base_form_kwargs):
        """
        Given a nested form config get the init arguments, should return args, kwargs

        :param nested_form_config: The nested form config
        :param args: The args that will be passed into the init method
        :param kwargs: The kwargs that will be passed into the init method
        :param base_form_args: The args that were given to the base form
        :param base_form_kwargs: The kwargs that were given to the base form
        """
        return args, kwargs

    def get_nested_form_save_args(self, nested_form_config, args, kwargs, base_form_args, base_form_kwargs):
        """
        Given a nested form config get the save arguments, should return args, kwargs

        :param nested_form_config: The nested form config
        :param args: The args that will be passed into the init method
        :param kwargs: The kwargs that will be passed into the init method
        :param base_form_args: The args that were given to the base form
        :param base_form_kwargs: The kwargs that were given to the base form
        """
        return args, kwargs

    def get_required_forms(self):
        """
        Checks which forms are required based on the params and returns a list of only the required forms
        :rtype: list of NestedFormConfig
        """
        return [nested_form for nested_form in self.nested_forms if self.form_is_required(nested_form)]

    def form_is_required(self, nested_form):
        """
        Handles the logic to check if an individual form is required
        """

        # Check the required flag
        if nested_form.required:
            return True

        # Ensure we have a require key
        if nested_form.required_key is None:
            return False

        # Create a boolean field to ensure that the required key is truthy
        boolean_field = forms.BooleanField(required=False)

        # Return if this value is truthy or not
        return boolean_field.clean(self.data.get(nested_form.required_key))

    def _clean_fields(self):
        """
        Cleans all of self.data and populates self._errors and
        self.cleaned_data.

        This is copied from django with an addition at the bottom
        """

        # Clean our nested fields first
        # Get our required forms
        required_forms = self.get_required_forms()

        # Clean our required nested form fields first
        for form in required_forms:
            # Get the errors and cleaned data
            errors = form.instance.errors
            cleaned_data = form.instance.cleaned_data

            # Add the errors
            if errors:
                self.add_error(form.key, list(errors.values()))
            # Update the data if we do not have any errors
            else:
                self.data[form.key] = cleaned_data

        # Call the parent clean method to clean our base fields
        return super(NestedFormMixin, self)._clean_fields()
