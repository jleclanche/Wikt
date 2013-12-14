from wtforms import Form, BooleanField, TextField, TextAreaField, validators


class DeleteForm(Form):
	summary = TextField("Reason", [validators.length(max=80)])
	watch_this = BooleanField("Watch this page")


class EditForm(Form):
	text = TextAreaField("Text")
	summary = TextField("Summary", validators=[validators.length(max=80)])
	minor_edit = BooleanField("This is a minor edit")
	watch_this = BooleanField("Watch this page")


class MoveForm(Form):
	target = TextField("To new title", [validators.length(max=80)])
	summary = TextField("Reason", [validators.length(max=80)])
	leave_redirect = BooleanField("Leave a redirect behind")
	# move_subpages
	watch_this = BooleanField("Watch this page")
