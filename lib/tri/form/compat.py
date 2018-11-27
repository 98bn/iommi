try:
    from django.core.exceptions import ValidationError
    from django.core.validators import validate_email, URLValidator
    from django.http import HttpResponse
    from django.template import RequestContext
    from django.template.loader import render_to_string
    from django.utils.html import format_html
    from django.utils.text import slugify
    from django.test import RequestFactory
    from django.http import HttpResponseRedirect
    from django.template import Template
    from django.shortcuts import render
    from django.utils.encoding import smart_text
    from django.template.context_processors import csrf
    from django import __version__ as django_version
    django_version = tuple([int(x) for x in django_version.split('.')])

    try:
        from django.template.loader import get_template_from_string
    except ImportError:  # pragma: no cover
        # Django 1.8+
        # noinspection PyUnresolvedReferences
        from django.template import engines

        def get_template_from_string(template_code, origin=None, name=None):
            del origin, name  # the origin and name parameters seems not to be implemented in django 1.8
            return engines['django'].from_string(template_code)

    def setup_db_compat():
        from tri.form import register_field_factory, Field, foreign_key_factory, many_to_many_factory
        from tri.declarative import setdefaults_path
        from django.db.models import IntegerField, FloatField, TextField, BooleanField, AutoField, CharField, \
            CommaSeparatedIntegerField, DateField, DateTimeField, DecimalField, EmailField, URLField, TimeField, \
            ForeignKey, ManyToManyField, FileField, ManyToOneRel, ManyToManyRel

        # The order here is significant because of inheritance structure. More specific must be below less specific.
        register_field_factory(CharField, Field)
        register_field_factory(URLField, Field.url)
        register_field_factory(TimeField, Field.time)
        register_field_factory(EmailField, Field.email)
        register_field_factory(DecimalField, Field.decimal)
        register_field_factory(DateField, Field.date)
        register_field_factory(DateTimeField, Field.datetime)
        register_field_factory(CommaSeparatedIntegerField, lambda **kwargs: Field.comma_separated(parent_field=Field.integer(**kwargs)))
        register_field_factory(BooleanField, lambda model_field, **kwargs: Field.boolean(model_field=model_field, **kwargs) if not model_field.null else Field.boolean_tristate(model_field=model_field, **kwargs))
        register_field_factory(TextField, Field.text)
        register_field_factory(FloatField, Field.float)
        register_field_factory(IntegerField, Field.integer)
        register_field_factory(AutoField, lambda **kwargs: Field.integer(**setdefaults_path(kwargs, show=False)))
        register_field_factory(ManyToOneRel, None)
        register_field_factory(ManyToManyRel, None)
        register_field_factory(FileField, Field.file)
        register_field_factory(ForeignKey, foreign_key_factory)
        register_field_factory(ManyToManyField, many_to_many_factory)

    def field_defaults_factory(model_field):
        from tri.form import capitalize
        from django.db.models import BooleanField
        r = {}
        if hasattr(model_field, 'verbose_name'):
            r['display_name'] = capitalize(model_field.verbose_name)

        if hasattr(model_field, 'null') and not isinstance(model_field, BooleanField):
            r['required'] = not model_field.null and not model_field.blank

        if hasattr(model_field, 'blank'):
            r['parse_empty_string_as_none'] = not model_field.blank

        return r

    def render_template(request, template, context):
        """
        @type request: django.http.HttpRequest
        @type template: str|django.template.Template|django.template.backends.django.Template
        @type context: dict
        """
        import six
        from tri.form.compat import Template
        if template is None:
            return ''
        elif isinstance(template, six.string_types):
            # positional arguments here to get compatibility with django 1.8+
            return render_to_string(template, context, request=request)
        elif isinstance(template, Template):
            return template.render(RequestContext(request, context))
        else:
            from django.template.backends.django import Template as Template2
            assert isinstance(template, Template2)
            return template.render(context, request)

except ImportError:
    from jinja2 import Markup
    from jinja2 import Template as _Template
    from flask import render_template as render
    from flask import Response as _Response
    from flask import Request as _Request

    django_version = None
    csrf = None

    class HttpResponse:
        def __init__(self, content, content_type=None):
            self.r = _Response(content, content_type=content_type)

        @property
        def content(self):
            return self.r.get_data()

        @property
        def _headers(self):
            return {k.lower(): [v] for k, v in self.r.headers._list}

    class HttpRequest:

        def __init__(self, environ):
            self.r = _Request(environ)

        @property
        def POST(self):
            return self.r.form

        @property
        def GET(self):
            return self.r.args

        @property
        def method(self):
            return self.r.method

    def format_html(format_string, *args, **kwargs):
        return Markup(format_string).format(*args, **kwargs)

    class RequestFactory:
        def method(self, method, url, params, body=None, root_path=None):
            from flask.ctx import AppContext
            from flask import Flask
            import os
            app = AppContext(Flask('tri_form', root_path=root_path or os.path.dirname(__file__)))
            app.push()
            from werkzeug.test import create_environ
            return HttpRequest(create_environ(path=url, query_string=params, method=method, data=body))

        def get(self, url, params=None):
            return self.method('GET', url, params=params)

        def post(self, url, params=None):
            return self.method('POST', url, params={}, body=params)

    class ValidationError(Exception):
        def __init__(self, messages):
            if isinstance(messages, list):
                self.messages = messages
            else:
                self.messages = [messages]

    def HttpResponseRedirect(url, code=302):
        from flask import redirect
        return redirect(url, code=code)

    def smart_text(s):
        return str(s)

    def render_template(request, template, context):
        if template is None:
            return ''

        if isinstance(template, str):
            return render(template, **(context or {}))
        else:
            return template.render(context=context, request=request)

    def validate_email(s):
        if '@' not in s:
            raise ValidationError(messages=['Enter a valid email address.'])

        return s

    class URLValidator:
        def __call__(self, string_value):
            if '://' not in string_value:
                raise ValidationError('Enter a valid URL.')

    def get_template_from_string(s, origin=None, name=None):
        return Template(s)

    def render_to_string(template_name, context, request=None):
        return format_html(render(template_name, request=request, **context))

    class Template:
        def __init__(self, template_string, **kwargs):
            self.template = _Template(template_string, **kwargs)

        def render(self, context, request=None):
            return self.template.render(**context)

    def slugify(s):
        return s.lower().replace(' ', '-')

    def setup_db_compat():
        pass

    def field_defaults_factory(model_field):
        raise NotImplementedError()