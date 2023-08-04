
Release Notes
=============

3.1.20
-----
* offset() does not consider timezone when reversing.

3.1.9
-----
* next_occurernce is only offset on save() if the object is new.
* clone_with_day_offset no longer calls clone() to ensure the clone is not saved with an id before day_offset is set.

3.1.8
-----
* Added RRule.day_offset to support true offset support. clone_with_day_offset method now sets day_offset.

3.1.7
-----
* RecurrenceForm will no longer refresh the next occurrence if the occurrence is expired.

3.1.6
-----
* Update migrations to point to utils time zone field

3.1.5
-----
* Support timezone field v4 all time zones

3.1.4
-----
* Use all pytz time zones by default

3.1.3
-----
* Fix import

3.1.2
-----
* Switch rrule to use our time zone field for cast-on-assign behavior

3.1.1
-----
* Django 4 support
* Switch off time zone field fork

3.0.3
-----
* Added the ability to set an exclusion rule on an rrule object

3.0.2
-----
* Add ability to set error_messages on activities

3.0.1
-----
* Restore forked timezone field for now. will be removed in 3.1
* Only support py 3.7 and django 2.2, 3.2. other versions will be restored in 3.1

3.0.0
-----
* Add support for python 3.8, 3.9
* Drop support for python 3.6
* Add support for Django 3.0, 3.1, 3.2, 4.0, 4.1
* Drop support for django 2.0, 2.1
* Switch to github actions
* Switched from ambition timezone field package to the main timezone field and set the requirement to < 5
* Added the cast-on-assignment behavior to this project as a mixin for models
* Added a subclass of timezone field which uses the cast-on-assign behavior

2.6.0
-----
* Added get_dates(start_date=) to calculate dates after start_date. Will replace get_dates.
* Added get_dates_from_params(start_date=) to calculate dates after start_date from rrule_params. Will replace generate_dates_from_params.

2.5.3
-----
* Fixed cloning when until param is present

2.5.2
-----
* Fixed cloning with bynweekday data

2.5.1
-----
* Updated the get_time_zone() helper method with pytz.all_timezones

2.5.0
-----
* Added support for byminute

2.4.0
-----
* Added rrule related object relation and object-level handling
* Added rrule clone_with_day_offset method
* Added rrule clone method

2.3.0
-----
* Added `value` and `previous_value` fields onto postgres lock
* Ability to pass a value into the `PostgresLockContext`
* [BREAKING] `PostgresLockContext` now returns itself and now the transaction

2.2.2
-----
* Fix recurrence bug in refresh_next_occurrence when recurrence is ending. Set next occurrence to null.

2.2.1
-----
* Testing utilities for transaction durable decorator

2.2.0
-----
* Added transaction module with durable decorator

2.1.0
-----
* Move rrule pre save code to a method
* Add rrule method to generate next occurrences without a need to save to db

2.0.0
-----
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
