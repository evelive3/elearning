# py_elearning

在中国人寿上班期间，会有定期的，基于[国寿E学]的线上学习。本意是好的，然而必须挂够课时这个设定真是无力吐槽，所以趁挂课时这段时间，我编写了一个基于Python Requests库的小东西，用于自动挂课时。

### requirements.
  - lxml
  - arrow
  - pycrypto
  - requests
  - xmltodict

### 安装依赖库

```sh
$ pip install -r requirements.txt
```


### 使用

```python
>>> user = User(usr, pwd)  # 实例化E学用户
>>> user.do_login()  # 登录E学
>>> user.get_course_list()  # 取得当前未学课程状态
>>> user.get_lesson()  # 取得一号课程详细列表
>>> user.start_course()  # 开始学第一课
>>> user.save_course()  # 保存进度
```


   [国寿E学]: <http://wwww.elearning.clic>
