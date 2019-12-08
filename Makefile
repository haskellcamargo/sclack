LINELENGTH := 100

normalize:
	isort -l$(LINELENGTH) -rc sclack
	black -t 'py38' -S -l$(LINELENGTH) sclack app.py
	pylint --py3k --rcfile=pylintrc sclack app.py
