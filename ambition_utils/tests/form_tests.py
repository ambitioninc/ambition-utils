from django import forms
from django.core.exceptions import ValidationError
from django.test import TestCase
from mock import MagicMock

from ambition_utils.forms import NestedFormMixin, NestedFormConfig
from ambition_utils.tests.models import FakeModel


class BadFormNoSave(NestedFormMixin, forms.Form):
    pass


class NestedForm1(NestedFormMixin, forms.Form):
    three = forms.CharField(error_messages={
        'required': 'Three is required'
    })
    four = forms.CharField(required=False)

    def __init__(self, init_number, *args, **kwargs):
        self.init_number = init_number
        super(NestedForm1, self).__init__(*args, **kwargs)

    def save(self, number):
        return {
            'init_number': self.init_number,
            'number': number
        }


class NestedForm2(NestedFormMixin, forms.Form):
    five = forms.CharField(error_messages={
        'required': 'Five is required'
    })
    six = forms.CharField(required=False)

    def __init__(self, init_user_id, *args, **kwargs):
        self.init_user_id = init_user_id
        super(NestedForm2, self).__init__(*args, **kwargs)

    def save(self, user_id):
        return {
            'init_user_id': self.init_user_id,
            'user_id': user_id
        }


class OptionalForm(NestedFormMixin, forms.Form):
    seven = forms.CharField(error_messages={
        'required': 'seven is required'
    })
    eight = forms.CharField(required=False)

    def save(self):
        return 'optional value'


class BadParentFormExistingField(NestedFormMixin, forms.Form):
    nested_form_configs = [
        NestedFormConfig(
            cls=NestedForm1,
            key='nested_form_1',
            pre=True,
        )
    ]

    # Duplicate form field from nested
    three = forms.CharField(error_messages={
        'required': 'Three is required'
    })


class ParentForm(NestedFormMixin, forms.Form):
    nested_form_configs = [
        NestedFormConfig(
            cls=NestedForm1,
            key='nested_form_1',
            required=False,
            required_key='nested_form_1_required',
            pre=True,
        ),
        NestedFormConfig(
            cls=NestedForm2,
            key='nested_form_2',
            required=False,
            required_key='nested_form_2_required',
            pre=True,
        ),
        NestedFormConfig(
            cls=OptionalForm,
            key='optional',
            required=False,
            field_prefix='optional_1',
            required_key='optional_required',
            pre=True,
        ),
        NestedFormConfig(
            cls=OptionalForm,
            key='optional_2',
            required=False,
            field_prefix='optional_2',
            required_key='optional_required_2',
            post=True,
        )
    ]

    one = forms.CharField(error_messages={
        'required': 'One is required'
    })
    two = forms.CharField(required=False)

    def get_nested_form_init_args(self, nested_form_config, args, kwargs, base_form_args, base_form_kwargs):
        if nested_form_config.key == 'nested_form_1':
            args = [1] + args
        elif nested_form_config.key == 'nested_form_2':
            args = [2] + args

        # Return the updated args
        return args, kwargs

    def get_nested_form_save_args(self, nested_form_config, args, kwargs, base_form_args, base_form_kwargs):
        if nested_form_config.key == 'nested_form_1':
            kwargs.update({
                'number': 10,
            })
        elif nested_form_config.key == 'nested_form_2':
            kwargs.update({
                'user_id': 5,
            })

        # Return the updated args
        return args, kwargs

    def save(self, *args, **kwargs):
        return 'the object'


class FormWithAlwaysRequired(NestedFormMixin, forms.Form):
    nested_form_configs = [
        NestedFormConfig(
            cls=NestedForm1,
            key='nested_form_1',
            required=True,
            pre=True
        ),
        NestedFormConfig(
            cls=NestedForm2,
            key='nested_form_2',
            required=True,
            pre=True
        ),
        NestedFormConfig(
            cls=OptionalForm,
            key='optional',
            required=True,
            pre=True
        )
    ]

    one = forms.CharField(error_messages={
        'required': 'One is required'
    })
    two = forms.CharField(required=False)


class FormWithOptional(NestedFormMixin, forms.Form):
    nested_form_configs = [
        NestedFormConfig(
            cls=NestedForm1,
            key='nested_form_1',
            required=False,
            required_key='nested_form_1_required',
            pre=True
        ),
        NestedFormConfig(
            cls=OptionalForm,
            key='optional',
            required=False,
            required_key='optional_required',
            pre=True
        )
    ]

    one = forms.CharField(error_messages={
        'required': 'One is required'
    })
    two = forms.CharField(required=False)

    def get_nested_form_init_args(self, nested_form_config, args, kwargs, base_form_args, base_form_kwargs):
        if nested_form_config.key == 'nested_form_1':
            args = [1] + args

        # Return the updated args
        return args, kwargs

    def save(self):
        return 'saved'


class ModelFormWithNestedForms(NestedFormMixin, forms.ModelForm):
    class Meta:
        model = FakeModel
        fields = ['name']

    nested_form_configs = [
        NestedFormConfig(
            cls=OptionalForm,
            key='optional',
            required=False,
            field_prefix='optional_1',
            required_key='optional_required',
            pre=True
        ),
        NestedFormConfig(
            cls=OptionalForm,
            key='optional_2',
            required=False,
            field_prefix='optional_2',
            required_key='optional_required_2',
            post=True
        )
    ]

    def save(self, commit=True, **kwargs):
        return super().save(commit=True)


class NestedFormMixinUnitTest(TestCase):
    """
    Unit tests for the nested form mixin
    """

    def test_bad_form_with_no_save_method(self):
        """
        Asssert that the form has a save method
        """

        with self.assertRaises(Exception):
            BadFormNoSave()

    def test_get_nested_form_init_args(self):
        """
        Checks return value of init args method
        """
        self.assertEqual(
            NestedFormMixin.get_nested_form_init_args(
                MagicMock(),
                nested_form_config=MagicMock(),
                args=['1'],
                kwargs={'one': 'one'},
                base_form_args=[],
                base_form_kwargs={}
            ),
            (['1'], {'one': 'one'})
        )

    def get_nested_form_save_args(self):
        """
        Checks return value of save args method
        """
        self.assertEqual(
            NestedFormMixin.get_nested_form_save_args(
                MagicMock(),
                nested_form_config=MagicMock(),
                args=['1'],
                kwargs={'one': 'one'},
                base_form_args=[],
                base_form_kwargs={}
            ),
            (['1'], {'one': 'one'})
        )

    def test_save(self):
        """
        Makes sure parent form save is called
        """
        class ParentForm1(forms.Form):
            def save(self):
                return 'saved'

        class ChildForm(NestedFormMixin, ParentForm1):
            pass

        form = ChildForm()
        self.assertEqual(form.save(), 'saved')

    def test_form_is_required(self):
        """
        Should return True when required is set, otherwise checks the flag value
        """

        # Create a test form
        class ParentForm1(NestedFormMixin, forms.Form):
            the_key = forms.BooleanField(required=False)

            def save(self):
                return 'saved'

        # Required in config
        nested_form = NestedFormConfig(
            cls=ParentForm1,
            key='one',
            required=True
        )
        form = ParentForm1(data={})
        self.assertTrue(form.is_valid())
        self.assertTrue(form.form_is_required(nested_form))

        # Required from flag
        nested_form = NestedFormConfig(
            cls=ParentForm1,
            key='one',
            required_key='the_key'
        )
        form = ParentForm1(data={
            'the_key': '1'
        })
        self.assertTrue(form.is_valid())
        self.assertTrue(form.form_is_required(nested_form))

        # Not required from flag
        nested_form = NestedFormConfig(
            cls=ParentForm1,
            key='one',
            required_key='the_key'
        )
        form = ParentForm1(data={})
        self.assertTrue(form.is_valid())
        self.assertFalse(form.form_is_required(nested_form))

        # Required key is None
        nested_form = NestedFormConfig(
            cls=ParentForm1,
            key='one',
            required=False,
            required_key=None
        )
        form = ParentForm1(data={})
        self.assertTrue(form.is_valid())
        self.assertFalse(form.form_is_required(nested_form))


class NestedFormMixinTest(TestCase):
    """
    Tests for the nested form mixin with normal non model forms
    """

    def test_duplicate_form_field_from_nested(self):
        """
        Test a form that has a duplicated form field from a nested form
        """

        with self.assertRaises(Exception):
            BadParentFormExistingField()

    def test_field_prefix_validation_error(self):
        """
        Makes sure a validation error is raised if two of the same form exist but both don't have a field prefix
        """
        class Form1(forms.Form):
            pass

        class ParentForm1(NestedFormMixin, forms.Form):
            nested_form_configs = [
                NestedFormConfig(cls=Form1, key='one'),
                NestedFormConfig(cls=Form1, key='two')
            ]

            def save(self):
                return 'saved'

        # Assert we raise a validation error from the two forms without a prefix
        with self.assertRaises(ValidationError):
            ParentForm1()

    def test_nested_required_fields(self):
        """
        The ParentForm required field and 2 of the nested forms' required fields should be required.
        The second optional form has a field prefix and provides the required field,
        so it should not cause an additional validation error.
        """
        data = {
            'nested_form_1_required': '1',
            'nested_form_2_required': '1',
            'optional_required_2': '1',
            'optional_2_seven': 'good'
        }

        form = ParentForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 3)

    def test_optional_form_flag_false(self):
        """
        Verifies an optional form is not required when its flag is false
        """
        data = {
            'nested_form_1_required': '1',
            'optional_required': 'False'
        }

        form = FormWithOptional(data=data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 2)

    def test_optional_form_flag_missing(self):
        """
        Verifies an optional form is not required when its flag is missing
        """
        data = {
            'nested_form_1_required': '1',
        }

        form = FormWithOptional(data=data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 2)

    def test_optional_form_flag_true(self):
        """
        Verifies an optional form is required when its flag is true
        """
        data = {
            'nested_form_1_required': 'True',
            'optional_required': 'True'
        }

        form = FormWithOptional(data=data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 3)

    def test_full_scenario(self):
        """
        Covers all presave, save, postsave scenarios with multiple forms
        """

        # Setup the testing data
        data = {
            'nested_form_1_required': '1',
            'nested_form_2_required': '1',
            'optional_required_2': '1',
            'one': '1',
            'three': '3',
            'five': '5',
            'seven': '7',
        }

        # Create the form
        form = ParentForm(data=data)

        # Assert that the form is valid
        self.assertTrue(form.is_valid())

        # Save the form
        return_value = form.save()

        # Assert that we have the proper return value
        self.assertEqual(return_value, 'the object')


class NestedModelFormMixinTest(TestCase):

    def test_save(self):
        """
        Verifies the model save still works as expected
        """

        # Create the data to submit
        data = {
            'name': 'just a fake name',
            'optional_required': 'True',
            'optional_required_2': 'True',
            'seven': '7',
        }

        # Create the form
        form = ModelFormWithNestedForms(data=data)

        # Assert the form is valid
        self.assertTrue(form.is_valid())

        # Save the form
        form.save(commit=True)

        # Get the model that was saved
        fake_model = FakeModel.objects.get()

        # Assert the model was saved correctly
        self.assertEqual(fake_model.name, 'just a fake name')
