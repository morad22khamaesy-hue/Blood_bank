from django import template

register = template.Library()

@register.filter(name="add_class")
def add_class(field, css):
    # מאחד class קיים עם החדש
    attrs = field.field.widget.attrs.copy()
    current = attrs.get("class", "")
    attrs["class"] = (current + " " + css).strip()
    return field.as_widget(attrs=attrs)
