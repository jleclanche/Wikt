from wtforms import Form, BooleanField, TextField, TextAreaField, validators

class EditForm(Form):
	text = TextAreaField("Text")
	summary = TextField("Summary")
	minor_edit = BooleanField("This is a minor edit")
	watch_this = BooleanField("Watch this page")
