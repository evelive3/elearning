#!/usr/bin/env python3
# -*- coding: utf-8 -*-


from urllib.parse import quote_plus, quote
from Crypto.Cipher import DES3
from arrow import Arrow
from lxml import etree
import xmltodict
import requests
import random
import re
import logging

logging.basicConfig(level=logging.DEBUG)


# TODO 使用偏函数包装每个页面访问时需要反馈的debug request cookie的logging信息
# TODO 在每个可能出错的地方加入raise
class User(object):
    def __init__(self, username, password):
        self.usr = username
        self.pwd = password
        self.last_response = None  # 每次执行不同方法后，都将最后访问的Response更新至此

        self.__base_url = 'http://www.elearning.clic'
        self.__des_key = 'YDuSFnJ0ubpN+d-vtyxcHBbv'
        self.__session = None  # TODO 为session添加一个方法，实现session为空或失效时，自动调用do_login()方法登陆
        self.__course = None
        self.__save_dict = None
        self.__script_session_id = None
        self.__course_lesson_dict = None
        self.__batch_id = 0

    def do_login(self):
        # 使用用户名密码登陆后返回有效session
        session = requests.session()
        _response = session.get('http://www.elearning.clic/ilearn/en/learner/jsp/login.jsp')  # 获取登陆页信息（cookie）
        # 加密用户名与密码
        # Input strings must be a multiple of 8 in length
        suffix_8bit = lambda x: x if (len(x) % 8 == 0) else x + ' ' * (8 - len(x) % 8)
        triple_des = DES3.new(self.__des_key)
        # encrypt plaintext and convert the hexadecimal representation of an integer
        # E学网站des3加密脚本有误，加密字段长并非8的倍数，其自动修正只是粗暴的在字段后增加8个空格
        # 使用本脚本，请先将E学密码更改为8的倍数长度
        self.usr = triple_des.encrypt(suffix_8bit(self.usr) + ' ' * 8).hex()
        self.pwd = triple_des.encrypt(suffix_8bit(self.pwd) + ' ' * 8).hex()
        login_data = dict(action1=1200, site='chinalife', srcreq=1001, tb_site_id='578ac43e4b4cdd4cc27c3cd70b2430b4',
                          tppd=self.pwd, tppd1='',
                          username=self.usr, username1='')
        _response = session.post('http://www.elearning.clic/ilearn/en/learner/jsp/authenticate.jsp', data=login_data)
        self.last_response = _response
        self.__session = session

    def get_course_list(self):
        # 获取课程状态
        if not self.__session:
            raise AttributeError('未获取有效的session对象')  # TODO 此sesseion判断并不严谨，需更改
        result = []
        now = int(Arrow.now().float_timestamp * 1000)  # generate javascript style timestamp
        _response = self.__session.get(
            'http://www.elearning.clic/ilearn/en/cst_learner2/jsp/home_my_course.jsp?_={time}'.format(
                time=now))  # 取得课程信息
        root = etree.HTML(_response.text)
        td_list = root.xpath(u'//span[@class="td_td_style"]')  # 查找有效表格
        a_list = root.xpath(u'//a[@title="Click to study"]')  # 查找有效课程url
        td_len = len(td_list)  # 取得有效td元素个数
        a_len = len(a_list)  # 取得有效链接个数
        if td_len is not 0 and a_len is not 0:
            # 如果找到有效td元素和a元素，就以每4组td生成一个字典
            for n in range(int(td_len / 4)):
                sub = 0 * n
                result.append({
                    'course_name': td_list[sub].text.strip(),
                    'course_section_rate': float(td_list[sub + 1].text.strip().partition('\n')[0]),
                    'course_time_rate': float(td_list[sub + 2].text.strip().partition('\n')[0]),
                    'course_finished': td_list[sub + 3].text.strip() == '已完成',
                    'course_url': a_list[n].attrib['href']
                })
        self.last_response = _response
        self.__course = result
        for k, v in enumerate(result):
            print('序号：{0} \t课名： {1}\t课程进度: {2}\t课时进度： {3}\t完成: {4}\n'.format(k, v['course_name'],
                                                                             v['course_section_rate'],
                                                                             v['course_time_rate'],
                                                                             v['course_finished'] is True))

    def get_lesson(self, n=0):
        # 获取课程详细XML
        course_url = self.__course[n]['course_url']  # 取得课件地址
        _response = self.__session.get(course_url)  # 取得点击开始学习按钮后的响应内容
        launch_content_list = re.findall(r'launchContent\((["\S"]*)\);', _response.text)[0].replace('"', '').split(
            ',')  # 取得launchContent内容字符串列表
        player_location_list = re.findall(r'player\.location.{1,3}"(\S*)"', _response.text)[0].split(
            '"+rco_id+"')  # 取得跳转网址拆分列表
        for n in range(len(player_location_list)):
            player_location_list[n] += "{%s}" % n
        rco_id = launch_content_list[0]
        classroom_id = launch_content_list[1]
        location_url = "".join(player_location_list).format(rco_id, classroom_id)  # 合并网址为有效网址
        location_request = self.__session.get(location_url)  # 访问第一级跳转页
        # 课程页面正式开始
        second_location = self.__base_url + re.findall(r'window.location\.href.{1,3}"(.*)";', location_request.text)[
            0]  # 获取跳转目标页网址
        # 获取课程列表XML
        # _response = self.__session.get(second_location)  # 刷个存在感
        _response = self.__session.get(
            'http://www.elearning.clic/ilearn/en/learner/jsp/player/player_left.jsp?rco_id={0}'.format(
                rco_id))  # 获取课程XML前置网页
        curr_node_id = re.findall(r"onTreeLoad\((\S*)\);", _response.text)[0].replace("'", '').split(",")[
            2]  # 获取curr_node_id
        course_xml = self.__session.get(
            'http://www.elearning.clic/ilearn/en/learner/jsp/player/load_lesson.jsp?rco_id={0}&curr_node_id={1}'.format(
                rco_id, curr_node_id)).text  # 课程列表xml get
        self.last_response = _response
        self.__course_lesson_dict = xmltodict.parse(course_xml)  # 懒得搞，直接转dict
        for k, v in enumerate(self.__course_lesson_dict['tree']['item']['item']):
            print('序号： {0}\t章节： {1}\t完成： {2}\n'.format(k, v['@text'], v['userdata'][0]['#text'] is 'R'))

    def start_course(self, n=0):
        # 刷课程，挂课时开始
        # 获取scriptSessionId in engine.js
        _response = self.__session.get('http://www.elearning.clic/ilearn/dwr/engine.js')
        script_session_id = re.findall(r"dwr.engine\._origScriptSessionId = (\S+);", _response.text)[0].replace('"',
                                                                                                                '')  # 取得原始scipteSessionId
        script_session_id += str(random.randint(0, 999))  # 等价于JavaScript中str + Math.floor(Math.random()*1000)
        choose_first_caption = self.__course_lesson_dict['tree']['item']['item'][n]['userdata']
        first_caption_url = 'http://www.elearning.clic/ilearn/en/learner/jsp/player/player_iframe.jsp?cdir={0}&ifile={1}&url={2}'.format(
            choose_first_caption[2]['#text'], choose_first_caption[3]['#text'],
            quote_plus(quote_plus(choose_first_caption[1]['#text'])))
        # 获取initData in player_iframe.jsp 并将其转化为字典
        _response = self.__session.get(first_caption_url)
        save_dict = {s.split(',')[0]: s.split(',')[1] for s in
                     map(lambda x: x.replace('"', ''), re.findall(r'[\w+]\.put\((.+)\)', _response.text))}
        self.__save_dict = save_dict
        self.__script_session_id = script_session_id
        self.last_response = _response

    def save_course(self):
        # 保存课时
        save_data = {
            'callCount': 1,
            'page': '/ilearn/en/learner/jsp/player/player_left.jsp?rco_id={0}'.format(self.__save_dict.get('rco_id')),
            'httpSessionId': self.last_response.cookies.get('JSESSIONID'),
            'scriptSessionId': self.__script_session_id,
            'c0-scriptName': 'lessonStudyData',
            'c0-methodName': 'updateRcoTreeList',
            'c0-id': 0,
            'c0-e1': 'string:' + self.__save_dict.get('rco_id'),
            'c0-e2': 'string:' + self.__save_dict.get('curr_rco_id'),
            'c0-e3': 'string:' + self.__save_dict.get('curr_rco_id'),
            'c0-e4': 'string:' + self.__save_dict.get('icr_id'),
            'c0-e5': 'string:' + self.__save_dict.get('user_id'),
            'c0-e6': 'string:' + self.__save_dict.get('tbc_id'),
            'c0-e7': 'string:' + self.__save_dict.get('site_id'),
            'c0-e8': 'string:' + self.__save_dict.get('cmi_core_lesson_status'),
            'c0-e9': 'string:' + self.__save_dict.get('cmi_core_score_raw'),
            'c0-e10': 'string:' + self.__save_dict.get('cmi_core_lesson_location'),
            'c0-e11': 'string:' + self.__save_dict.get('cmi_suspend_data'),
            'c0-e12': 'string:' + self.__save_dict.get('cmi_core_session_time'),
            'c0-e13': 'string:' + self.__save_dict.get('cmi_mastery_score'),
            'c0-e14': 'string:' + self.__save_dict.get('cmi_core_credit'),
            'c0-e15': 'string:' + quote(self.__save_dict.get('start_time')),
            'c0-e16': 'string:' + quote(Arrow.now().isoformat(sep='\u0020').split('.')[0]),
            'c0-e17': 'string:' + self.__save_dict.get('pre_score'),
            'c0-e18': 'string:' + self.__save_dict.get('pre_status'),
            'c0-e19': 'string:' + self.__save_dict.get('pre_location'),
            'c0-e20': 'string:' + self.__save_dict.get('pre_suspend_data'),
            'c0-e21': 'string:' + self.__save_dict.get('effectivelength'),
            'c0-e22': 'string:' + self.__save_dict.get('is_lesson_time'),
            'c0-e23': 'string:' + self.__save_dict.get('tracking_type'),
            'c0-e24': 'string:' + self.__save_dict.get('attempt_num_flag'),
            'c0-param0': 'Object_Object:{rco_id:reference:c0-e1, pre_rco_id:reference:c0-e2, curr_rco_id:reference:c0-e3, icr_id:reference:c0-e4, user_id:reference:c0-e5, tbc_id:reference:c0-e6, site_id:reference:c0-e7, cmi_core_lesson_status:reference:c0-e8, cmi_core_score_raw:reference:c0-e9, cmi_core_lesson_location:reference:c0-e10, cmi_suspend_data:reference:c0-e11, cmi_core_session_time:reference:c0-e12, cmi_mastery_score:reference:c0-e13, cmi_core_credit:reference:c0-e14, start_time:reference:c0-e15, start_study_time:reference:c0-e16, pre_score:reference:c0-e17, pre_status:reference:c0-e18, pre_location:reference:c0-e19, pre_suspend_data:reference:c0-e20, effectivelength:reference:c0-e21, is_lesson_time:reference:c0-e22, tracking_type:reference:c0-e23, attempt_num_flag:reference:c0-e24}',
            'c0-param1': 'string:U',
            'batchId': self.__batch_id
        }
        self.__batch_id += 1
        _response = self.__session.post(
            'http://www.elearning.clic/ilearn/dwr/call/plaincall/lessonStudyData.updateRcoTreeList.dwr',
            save_data)
        self.last_response = _response

    def get_page(self, url):
        # 用于动态调试
        return self.__session.get(url)


if __name__ == '__main__':
    usr = input('username')
    pwd = input('password')
    user = User(usr, pwd)  # 实例化E学用户
    user.do_login()  # 登录E学
    user.get_course_list()  # 取得当前未学课程状态
    user.get_lesson()  # 取得一号课程详细列表
    user.start_course()  # 开始学第一课
    user.save_course()  # 保存进度
