Release Notes
=============

2.0.0
-----
* Add support for python 3.8
* Add add support for django 3.0, 3.1
* Drop support for django 2.0, 2.1

1.2.1
-----
* Use copy instead of deep copy on form data and files because deepcopy tries to serialize all objects including file types, which isn't always possible

1.2.0
-----
* Added support for passing an rrule object id in the recurrence form

1.1.3
-----
* Fixed time zone object access in rrule model

1.1.2
-----
* Fixed submitted from from being excluded in nested_form_kwargs
* Renamed run_tests
* Updated Django version pinning

1.1.1
-----
* Fix rrule queryset to correctly limit rrule objects to progress

1.0.3
-----
* Deep copy custom nested form error messages so it doesn't overwrite the parent class's error message

1.0.2
-----
* Added support for last day of month

1.0.1
-----
* Reverted save existing recurrence functionality to not make assumptions about the next occurrence

1.0.0
-----
* Django 2.1, Django 2.2, Python 3.7 tests
* Dropped Django 1.11, Python < 3.6
* Allow modifying rrule next occurrence date

0.8.0
-----
* Refactored nested forms to simplify the api and make it more robust

BREAKING CHANGES (NestedFormMixin)

* No longer calls `form_save`. The base form and all mixin forms are required to have a `save` method
* Renamed `get_pre_save_method_kwargs` and `get_post_save_method_kwargs` to `get_nested_form_save_args`
* Removed `NestedModelFormMixin`, please use `NestedFormMixin` for all types of forms

0.6.1
-----
* Fixed bug with rrule future occurrences using time zones ahead of UTC

0.6.0
-----
* Added postgres lock app

0.4.0
-----
* Updated activity to include a reference to a context object and attributes to track completion as a ratio

0.3.0
-----
* Use tox to test more versions

0.2.0
-----
* Added mixin for tasks to add progress tracking

0.1.2
-----
* Do not modify the same dict while iterating

0.1.1
-----
* Use form config class to more easily control and document arguments

0.1.0
-----
* This is the initial release of ambition-utils
