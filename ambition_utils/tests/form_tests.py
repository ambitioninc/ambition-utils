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

    def save(self, *args, **kwargs):
        return kwargs['number'] * 10


class NestedForm2(NestedFormMixin, forms.Form):
    five = forms.CharField(error_messages={
        'required': 'Five is required'
    })
    six = forms.CharField(required=False)

    def save(self, *args, **kwargs):
        return 2


class OptionalForm(NestedFormMixin, forms.Form):
    seven = forms.CharField(error_messages={
        'required': 'seven is required'
    })
    eight = forms.CharField(required=False)

    def save(self, *args, **kwargs):
        return 'optional value'


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

    def get_pre_save_method_kwargs(self):
        return {
            'number': 10,
            'another_number': 'ten'
        }

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

    # Flags for the 3 nested forms
    nested_form_1_required = forms.BooleanField(required=False)
    nested_form_2_required = forms.BooleanField(required=False)
    optional_required = forms.BooleanField(required=False)


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

    # Flags for the 2 nested forms
    nested_form_1_required = forms.BooleanField(required=False)
    optional_required = forms.BooleanField(required=False)

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

    def test_get_pre_save_method_kwargs(self):
        """
        Checks return value of pre save method
        """
        self.assertEqual(
            NestedFormMixin.get_pre_save_method_kwargs(MagicMock()),
            {}
        )

    def test_get_post_save_method_kwargs(self):
        """
        Checks return value of post save method
        """
        self.assertEqual(
            NestedFormMixin.get_post_save_method_kwargs(
                MagicMock(),
                one='two'
            ),
            {'one': 'two'}
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
