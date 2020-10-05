# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
# isort:skip_file
"""Unit tests for Superset"""
import json

from flask import Response
import prison
from pytest import mark
from superset import app
from superset.views.base import generate_download_headers
from tests.base_api_tests import ApiOwnersTestCaseMixin
from tests.dashboards.consts import *
from tests.dashboards.base_case import DashboardTestCase
from tests.dashboards.superset_factory_util import create_dashboard_to_db
from tests.dashboards.dashboard_test_utils import *

@mark.ofek
class TestDashboardApi(DashboardTestCase, ApiOwnersTestCaseMixin):
    resource_name = "dashboard"

    dashboard_data = {
        "dashboard_title": "title1_changed",
        "slug": "slug1_changed",
        "position_json": '{"b": "B"}',
        "css": "css_changed",
        "json_metadata": '{"refresh_frequency": 30}',
        "published": False,
    }

    def tearDown(self):
        self.clean_created_objects()

    def test_a_get_dashboard__exists_dashboard(self):
        """
        Dashboard API: Test get dashboard
        """
        # arrange
        admin = self.get_user("admin")
        dashboard = create_dashboard_to_db(random_title(), random_slug(), owners=[admin])
        expected_result = {
            "changed_by": None,
            "changed_by_name": "",
            "changed_by_url": "",
            "charts": [],
            "id": dashboard.id,
            "css": "",
            "dashboard_title": dashboard.dashboard_title,
            "json_metadata": "",
            "owners": [
                {
                    "id": 1,
                    "username": "admin",
                    "first_name": "admin",
                    "last_name": "user",
                }
            ],
            "position_json": "",
            "published": False,
            "url": GET_DASHBOARD_VIEW_URL_FORMAT.format(dashboard.slug),
            "slug": dashboard.slug,
            "table_names": "",
            "thumbnail_url": dashboard.thumbnail_url,
        }
        self.login(username="admin")

        # act
        response = self.get_dashboard_via_api_by_id(dashboard.id)

        # assert
        self.assert200(response)
        self.__assert_get_dashboard_response(response, expected_result)

    def __assert_get_dashboard_response(self, response, expected_result):
        responseDataResult = json.loads(response.data.decode("utf-8"))["result"]
        self.assertIn("changed_on", responseDataResult)
        for key, value in responseDataResult.items():
            # We can't assert timestamp values
            if key != "changed_on":
                self.assertEqual(value, expected_result[key])

    def test_a_get_dashboard_not_exists__404_response(self):
        """
        Dashboard API: Test get dashboard not found
        """
        # arrange
        max_id = get_max_dashboard_id()
        self.login(username="admin")

        # act
        rv = self.get_dashboard_via_api_by_id(max_id + 1)

        # assert
        self.assert404(rv)

    def test_info_dashboard(self):
        """
        Dashboard API: Test info
        """

        # arrange
        self.login(username="admin")
        uri = DASHBOARDS_API_URL + "_info"

        # act
        rv = self.get_assert_metric(uri, "info")

        # assert
        self.assert200(rv)

    def test_a_get_dashboards_changed_on(self):
        """
        Dashboard API: Test get dashboards changed on
        """

        # arrange
        from datetime import datetime
        import humanize

        admin = self.get_user("admin")
        start_changed_on = datetime.now()
        create_dashboard_to_db(random_title(), random_slug(), owners=[admin])

        self.login(username="admin")

        arguments = {
            "order_column": "changed_on_delta_humanized",
            "order_direction": "desc",
        }
        uri = DASHBOARDS_API_URL_WITH_QUERY_FORMAT.format(prison.dumps(arguments))

        # act
        rv = self.get_assert_metric(uri, "get_list")

        # assert
        self.assert200(rv)
        data = json.loads(rv.data.decode("utf-8"))
        self.assertEqual(
            data["result"][0]["changed_on_delta_humanized"],
            humanize.naturaltime(datetime.now() - start_changed_on),
        )

    def test_a_get_dashboards_filter(self):
        """
        Dashboard API: Test get dashboards filter
        """
        admin = self.get_user("admin")
        gamma = self.get_user("gamma")
        title = random_title()
        create_dashboard_to_db(title, random_slug(), owners=[admin, gamma])

        self.login(username="admin")

        arguments = {
            "filters": [{"col": "dashboard_title", "opr": "sw", "value": title[0:-1]}]
        }
        uri = DASHBOARDS_API_URL_WITH_QUERY_FORMAT.format(prison.dumps(arguments))

        rv = self.get_assert_metric(uri, "get_list")
        self.assert200(rv)
        data = json.loads(rv.data.decode("utf-8"))
        self.assertEqual(data["count"], 1)

        arguments = {
            "filters": [
                {"col": "owners", "opr": "rel_m_m", "value": [admin.id, gamma.id]}
            ]
        }
        uri = DASHBOARDS_API_URL_WITH_QUERY_FORMAT.format(prison.dumps(arguments))
        rv = self.client.get(uri)
        self.assert200(rv)
        data = json.loads(rv.data.decode("utf-8"))
        self.assertEqual(data["count"], 1)

    def test_a_get_dashboards_custom_filter(self):
        """
        Dashboard API: Test get dashboards custom filter
        """
        admin = self.get_user("admin")
        create_dashboard_to_db("foo_a", "ZY_bar", owners=[admin])
        create_dashboard_to_db("zy_foo", "slug1", owners=[admin])
        create_dashboard_to_db("foo_b", "slug1zy_", owners=[admin])
        create_dashboard_to_db("bar", "foo", owners=[admin])

        arguments = {
            "filters": [
                {"col": "dashboard_title", "opr": "title_or_slug", "value": "zy_"}
            ],
            "order_column": "dashboard_title",
            "order_direction": "asc",
            "keys": ["none"],
            "columns": ["dashboard_title", "slug"],
        }
        self.login(username="admin")
        uri = DASHBOARDS_API_URL_WITH_QUERY_FORMAT.format(prison.dumps(arguments))
        rv = self.client.get(uri)
        self.assert200(rv)
        data = json.loads(rv.data.decode("utf-8"))
        self.assertEqual(data["count"], 3)

        expected_response = [
            {"slug": "ZY_bar", "dashboard_title": "foo_a"},
            {"slug": "slug1zy_", "dashboard_title": "foo_b"},
            {"slug": "slug1", "dashboard_title": "zy_foo"},
        ]
        for index, item in enumerate(data["result"]):
            self.assertEqual(item["slug"], expected_response[index]["slug"])
            self.assertEqual(
                item["dashboard_title"], expected_response[index]["dashboard_title"]
            )

        self.logout()
        self.login(username="gamma")
        uri = DASHBOARDS_API_URL_WITH_QUERY_FORMAT.format(prison.dumps(arguments))
        rv = self.client.get(uri)
        self.assert200(rv)
        data = json.loads(rv.data.decode("utf-8"))
        self.assertEqual(data["count"], 0)

    @mark.skipif(
        is_dashboard_level_access_enabled(),
        reason="deprecated test, when DashboardLevelAccess flag is enabled",
    )
    def test_c_delete_dashboard(self):
        """
        Dashboard API: Test delete
        """
        admin = self.get_user("admin")
        dashboard_id = create_dashboard_to_db(f"title{random_str()}", "slug1",
                                              owners=[admin]).id
        self.login(username="admin")
        rv = self.delete_dashboard_via_api(dashboard_id)
        self.assert200(rv)
        self.assert_dashboard_deleted(dashboard_id)

    @mark.skipif(
        not is_dashboard_level_access_enabled(),
        reason="DashboardLevelAccess flag is not disable",
    )
    def test_c_delete_dashboard_with_dashboard_level_access(self):
        """
        Dashboard API: Test delete
        """
        admin = self.get_user("admin")
        dashboard = create_dashboard_to_db(f"title{random_str()}", "slug1", owners=[admin])
        assign_dashboard_permissions_to_multiple_roles(dashboard)
        dashboard_id = dashboard.id
        self.login(username="admin")

        # act
        rv = self.delete_dashboard_via_api(dashboard_id)

        # assert
        self.assert200(rv)
        self.assert_dashboard_deleted(dashboard_id)
        self.assert_permissions_were_deleted(dashboard)
        clean_dashboard_matching_roles()

    def test_c_delete_not_found_dashboard(self):
        """
        Dashboard API: Test not found delete
        """
        self.login(username="admin")
        dashboard_id = 1000
        rv = self.delete_dashboard_via_api(dashboard_id)
        self.assert404(rv)

    def test_c_delete_dashboard_admin_not_owned(self):
        """
        Dashboard API: Test admin delete not owned
        """
        gamma = self.get_user("gamma")
        dashboard_id = create_dashboard_to_db(f"title{random_str()}", "slug1",
                                              owners=[gamma]).id

        self.login(username="admin")
        rv = self.delete_dashboard_via_api(dashboard_id)
        self.assert200(rv)
        self.assert_dashboard_deleted(dashboard_id)

    def test_c_delete_dashboard_not_owned(self):
        """
        Dashboard API: Test delete try not owned
        """
        user_alpha1 = self.create_user(
            "alpha1", "password", "Alpha", email="alpha1@superset.org"
        )
        self.create_user("alpha2", "password", "Alpha", email="alpha2@superset.org")

        existing_slice = get_slice_by_name("Girl Name Cloud")
        dashboard_id = create_dashboard_to_db(f"title{random_str()}", "slug1",
                                              published=True, owners=[user_alpha1],
                                              slices=[existing_slice]).id
        self.login(username="alpha2", password="password")
        rv = self.delete_dashboard_via_api(dashboard_id)
        self.assert403(rv)

    def test_d_delete_bulk_dashboards(self):
        """
        Dashboard API: Test delete bulk
        """
        admin = self.get_user("admin")
        dashboard_count = 4
        dashboard_ids = list()
        for dashboard_name_index in range(dashboard_count):
            dashboard_ids.append(
                create_dashboard_to_db(f"title{dashboard_name_index}",
                                       f"slug{dashboard_name_index}", owners=[admin]).id
            )
        self.login(username="admin")

        # act
        rv = self.bulk_delete_dashboard_via_api(dashboard_ids)

        self.assert200(rv)
        response = json.loads(rv.data.decode("utf-8"))
        expected_response = {"message": f"Deleted {dashboard_count} dashboards"}
        self.assertEqual(response, expected_response)
        for dashboard_id in dashboard_ids:
            self.assert_dashboard_deleted(dashboard_id)

    def test_d_delete_bulk_dashboards_bad_request(self):
        """
        Dashboard API: Test delete bulk bad request
        """
        dashboard_ids = [1, "a"]
        self.login(username="admin")

        # act
        rv = self.bulk_delete_dashboard_via_api(dashboard_ids)

        self.assert400(rv)

    def test_d_delete_bulk_dashboards_not_found(self):
        """
        Dashboard API: Test delete bulk not found
        """
        dashboard_ids = [1001, 1002]
        self.login(username="admin")

        # act
        rv = self.bulk_delete_dashboard_via_api(dashboard_ids)

        self.assert404(rv)

    def test_d_delete_bulk_dashboards_admin_not_owned(self):
        """
        Dashboard API: Test admin delete bulk not owned
        """
        gamma = self.get_user("gamma")
        dashboard_count = 4
        dashboard_ids = list()
        for dashboard_name_index in range(dashboard_count):
            dashboard_ids.append(
                create_dashboard_to_db(f"title{dashboard_name_index}",
                                       f"slug{dashboard_name_index}", owners=[gamma]).id
            )

        self.login(username="admin")
        # act
        rv = self.bulk_delete_dashboard_via_api(dashboard_ids)

        # assert
        self.assert200(rv)
        response = json.loads(rv.data.decode("utf-8"))
        expected_response = {"message": f"Deleted {dashboard_count} dashboards"}
        self.assertEqual(response, expected_response)

        for dashboard_id in dashboard_ids:
            self.assert_dashboard_deleted(dashboard_id)

    def test_d_delete_bulk_dashboards_not_owned(self):
        """
        Dashboard API: Test delete bulk try not owned
        """
        user_alpha1 = self.create_user(
            "alpha1", "password", "Alpha", email="alpha1@superset.org"
        )
        user_alpha2 = self.create_user(
            "alpha2", "password", "Alpha", email="alpha2@superset.org"
        )

        existing_slice = get_slice_by_name("Girl Name Cloud")

        dashboard_count = 4
        dashboards = list()
        for dashboard_name_index in range(dashboard_count):
            dashboards.append(
                create_dashboard_to_db(f"title{dashboard_name_index}",
                                       f"slug{dashboard_name_index}", published=True,
                                       owners=[user_alpha1], slices=[existing_slice])
            )

        owned_dashboard = create_dashboard_to_db("title_owned", "slug_owned",
                                                 published=True,
                                                 owners=[user_alpha2],
                                                 slices=[existing_slice])

        self.login(username="alpha2", password="password")

        # verify we can't delete not owned dashboards
        dashboard_ids = [dashboard.id for dashboard in dashboards]

        # act 1
        rv = self.bulk_delete_dashboard_via_api(dashboard_ids)

        # assert 1
        self.assert403(rv)
        response = json.loads(rv.data.decode("utf-8"))
        expected_response = {"message": "Forbidden"}
        self.assertEqual(response, expected_response)

        # act 2 - nothing is deleted in bulk with a list of owned and not owned dashboards
        rv = self.bulk_delete_dashboard_via_api(dashboard_ids + [owned_dashboard.id])

        # assert 2
        self.assert403(rv)
        response = json.loads(rv.data.decode("utf-8"))
        expected_response = {"message": "Forbidden"}
        self.assertEqual(response, expected_response)

    def create_dashboard(self, dashboard_data: Dict) -> Response:
        return self.post_assert_metric(DASHBOARDS_API_URL, dashboard_data, "post")

    def test_b_create_dashboard(self):
        """
        Dashboard API: Test create dashboard
        """

        # arrange
        admin_id = self.get_user("admin").id
        dashboard_data = {
            "dashboard_title": random_title(),
            "slug": random_slug(),
            "owners": [admin_id],
            "position_json": '{"a": "A"}',
            "css": "css",
            "json_metadata": '{"refresh_frequency": 30}',
            "published": True,
        }
        self.login(username="admin")

        # act
        rv = self.create_dashboard(dashboard_data)

        # assert
        self.assertStatus(rv, 201)
        data = json.loads(rv.data.decode("utf-8"))
        created_dashboard_id = data.get("id")
        model = get_dashboard_by_id(data.get("id"))
        if is_dashboard_level_access_enabled():
            self.assert_permission_was_created(model)

        # post
        self.delete_dashboard(created_dashboard_id)

    def test_b_create_simple_dashboard(self):
        """
        Dashboard API: Test create simple dashboard
        """

        # arrange
        dashboard_data = {"dashboard_title": "title1"}
        self.login(username="admin")

        # act
        rv = self.create_dashboard(dashboard_data)

        # assert
        self.assertStatus(rv, 201)
        data = json.loads(rv.data.decode("utf-8"))
        created_dashboard_id = data.get("id")
        get_dashboard_by_id(created_dashboard_id)

        # post
        self.delete_dashboard(created_dashboard_id)

    def test_b_create_dashboard_empty_data(self):
        """
        Dashboard API: Test create empty
        """

        # arrange
        dashboard_data = {}
        self.login(username="admin")

        # act
        rv = self.create_dashboard(dashboard_data)

        # assert
        self.assertStatus(rv, 201)

        # post
        data = json.loads(rv.data.decode("utf-8"))
        created_dashboard_id = data.get("id")
        self.delete_dashboard(created_dashboard_id)

    def test_b_create_dashboard_only_title(self):
        """
        Dashboard API: Test create empty
        """

        # arrange
        self.login(username="admin")
        dashboard_data = {"dashboard_title": ""}

        # act
        rv = self.create_dashboard(dashboard_data)

        # assert
        self.assertStatus(rv, 201)

        # post
        data = json.loads(rv.data.decode("utf-8"))
        created_dashboard_id = data.get("id")
        self.delete_dashboard(created_dashboard_id)

    def test_b_create_dashboard_validate_title(self):
        """
        Dashboard API: Test create dashboard validate title
        """

        # arrange
        dashboard_data = {"dashboard_title": "a" * 600}
        self.login(username="admin")

        # act
        rv = self.create_dashboard(dashboard_data)

        # assert
        self.assert400(rv)
        response = json.loads(rv.data.decode("utf-8"))
        expected_response = {
            "message": {"dashboard_title": ["Length must be between 0 and 500."]}
        }
        self.assertEqual(response, expected_response)

    def test_b_create_dashboard_validate_slug(self):
        """
        Dashboard API: Test create validate slug
        """

        # arrange
        admin = self.get_user("admin")
        create_dashboard_to_db("title1", "slug1", owners=[admin])
        self.login(username="admin")

        # Check for slug uniqueness
        dashboard_data = {"dashboard_title": "title2", "slug": "slug1"}
        # act
        rv = self.create_dashboard(dashboard_data)
        self.assertStatus(rv, 422)
        response = json.loads(rv.data.decode("utf-8"))
        expected_response = {"message": {"slug": ["Must be unique"]}}
        self.assertEqual(response, expected_response)

        # Check for slug max size
        dashboard_data = {"dashboard_title": "title2", "slug": "a" * 256}
        rv = self.create_dashboard(dashboard_data)
        self.assert400(rv)
        response = json.loads(rv.data.decode("utf-8"))
        expected_response = {"message": {"slug": ["Length must be between 1 and 255."]}}
        self.assertEqual(response, expected_response)

    def test_b_create_dashboard_validate_owners(self):
        """
        Dashboard API: Test create validate owners
        """

        # arrange
        dashboard_data = {"dashboard_title": "title1", "owners": [1000]}
        self.login(username="admin")
        # act
        rv = self.create_dashboard(dashboard_data)
        self.assertStatus(rv, 422)
        response = json.loads(rv.data.decode("utf-8"))
        expected_response = {"message": {"owners": ["Owners are invalid"]}}
        self.assertEqual(response, expected_response)

    def test_b_create_dashboard_invalid_position_json(self):
        """
        Dashboard API: Test create validate json
        """

        # arrange
        dashboard_data = {"dashboard_title": "title1", "position_json": '{"A:"a"}'}
        self.login(username="admin")

        # act
        rv = self.create_dashboard(dashboard_data)

        # assert
        self.assert400(rv)

    def test_b_create_dashboard_invalid_json_metadata(self):
        """
        Dashboard API: Test create validate json
        """

        # arrange
        self.login(username="admin")
        dashboard_data = {"dashboard_title": "title1", "json_metadata": '{"A:"a"}'}

        # act
        rv = self.create_dashboard(dashboard_data)

        # assert
        self.assert400(rv)

    def test_b_create_dashboard_invalid_refresh_frequency(self):
        """
        Dashboard API: Test create validate json
        """

        # arrange
        self.login(username="admin")
        dashboard_data = {
            "dashboard_title": "title1",
            "json_metadata": '{"refresh_frequency": "A"}',
        }

        # act
        rv = self.create_dashboard(dashboard_data)

        # assert
        self.assert400(rv)

    def update_dashboard(self, dashboard_id: int, dashboard_data: Dict) -> Response:
        uri = DASHBOARD_API_URL_FORMAT.format(dashboard_id)
        return self.put_assert_metric(uri, dashboard_data, "put")

    def test_update_dashboard(self):
        """
        Dashboard API: Test update
        """
        view_menu_id = None
        dashboard_level_access_enabled = (
            is_dashboard_level_access_enabled()
        )
        admin = self.get_user("admin")
        dashboard = create_dashboard_to_db(random_title(), random_slug(), owners=[admin])
        if dashboard_level_access_enabled:
            view_menu_id = security_manager.find_view_menu(dashboard.view_name).id
        dashboard_id = dashboard.id
        self.login(username="admin")
        title_field = "dashboard_title"

        dashboard_data_clone = self.dashboard_data.copy()
        dashboard_data_clone[title_field] = random_title()

        # act
        rv = self.update_dashboard(dashboard_id, dashboard_data_clone)

        # assert
        self.assert200(rv)
        model = get_dashboard_by_id(dashboard_id)
        self.assertEqual(model.dashboard_title, dashboard_data_clone[title_field])
        self.assertEqual(model.slug, dashboard_data_clone["slug"])
        self.assertEqual(model.position_json, dashboard_data_clone["position_json"])
        self.assertEqual(model.css, dashboard_data_clone["css"])
        self.assertEqual(model.json_metadata, dashboard_data_clone["json_metadata"])
        self.assertEqual(model.published, dashboard_data_clone["published"])
        self.assertEqual(model.owners, [admin])
        if dashboard_level_access_enabled:
            self.assert_permission_kept_and_changed(model, view_menu_id)

    def test_update_dashboard_chart_owners(self):
        """
        Dashboard API: Test update chart owners
        """
        user_alpha1 = self.create_user(
            "alpha1", "password", "Alpha", email="alpha1@superset.org"
        )
        user_alpha2 = self.create_user(
            "alpha2", "password", "Alpha", email="alpha2@superset.org"
        )
        admin = self.get_user("admin")
        slices = [get_slice_by_name("Girl Name Cloud"), get_slice_by_name("Trends"),
                  get_slice_by_name("Boys")]

        dashboard_id = create_dashboard_to_db(random_title(), random_slug(),
                                              owners=[admin], slices=slices).id
        self.login(username="admin")
        dashboard_data = {"owners": [user_alpha1.id, user_alpha2.id]}

        # act
        rv = self.update_dashboard(dashboard_id, dashboard_data)

        # assert
        self.assert200(rv)

        # verify slices owners include alpha1 and alpha2 users
        slices_ids = [_slice.id for _slice in slices]
        # Refetch Slices
        slices = (
            appbuilder.get_session.query(Slice).filter(Slice.id.in_(slices_ids)).all()
        )
        for _slice in slices:
            self.assertIn(user_alpha1, _slice.owners)
            self.assertIn(user_alpha2, _slice.owners)
            self.assertIn(admin, _slice.owners)
            # Revert owners on slice
            _slice.owners = []
            appbuilder.get_session.commit()

    @mark.update_name_error
    def test_update_partial_dashboard(self):
        """
        Dashboard API: Test update partial
        """
        admin = self.get_user("admin")
        dashboard_id = create_dashboard_to_db(random_title(), f"slug1{random_str()}",
                                              owners=[admin]).id
        self.login(username="admin")

        rv = self.update_dashboard(dashboard_id, {
            "json_metadata": self.dashboard_data["json_metadata"]})
        self.assert200(rv)

        changed_title = random_title()
        rv = self.update_dashboard(dashboard_id, {"dashboard_title": changed_title})
        self.assert200(rv)

        new_slug = random_slug()
        rv = self.update_dashboard(dashboard_id, {"slug": new_slug})
        self.assert200(rv)

        model = get_dashboard_by_id(dashboard_id)
        self.assertEqual(model.json_metadata, self.dashboard_data["json_metadata"])
        self.assertEqual(model.dashboard_title, changed_title)
        self.assertEqual(model.slug, new_slug)

    def test_update_published(self):
        """
        Dashboard API: Test update published patch
        """
        admin = self.get_user("admin")
        gamma = self.get_user("gamma")

        slug = random_slug()
        dashboard_id = create_dashboard_to_db(random_title(), slug,
                                              owners=[admin, gamma]).id
        dashboard_data = {"published": True}
        self.login(username="admin")

        rv = self.update_dashboard(dashboard_id, dashboard_data)

        self.assert200(rv)
        model = get_dashboard_by_id(dashboard_id)
        self.assertEqual(model.published, True)
        self.assertEqual(model.slug, slug)
        self.assertIn(admin, model.owners)
        self.assertIn(gamma, model.owners)

    def test_update_dashboard_new_owner(self):
        """
        Dashboard API: Test update set new owner to current user
        """
        gamma = self.get_user("gamma")
        admin = self.get_user("admin")
        dashboard_id = create_dashboard_to_db("title1", "slug1", owners=[gamma]).id
        dashboard_data = {"dashboard_title": "title1_changed"}
        self.login(username="admin")

        rv = self.update_dashboard(dashboard_id, dashboard_data)

        self.assert200(rv)
        model = get_dashboard_by_id(dashboard_id)
        self.assertIn(admin, model.owners)
        for slc in model.slices:
            self.assertIn(admin, slc.owners)

    def test_update_dashboard_slug_formatting(self):
        """
        Dashboard API: Test update slug formatting
        """
        admin = self.get_user("admin")
        dashboard_id = create_dashboard_to_db("title1", "slug1", owners=[admin]).id
        dashboard_data = {"dashboard_title": "title1_changed", "slug": "slug1 changed"}
        self.login(username="admin")
        rv = self.update_dashboard(dashboard_id, dashboard_data)
        self.assert200(rv)
        model = get_dashboard_by_id(dashboard_id)
        self.assertEqual(model.dashboard_title, "title1_changed")
        self.assertEqual(model.slug, "slug1-changed")

    def test_update_dashboard_validate_slug(self):
        """
        Dashboard API: Test update validate slug
        """
        admin = self.get_user("admin")
        slug_1 = random_slug()
        create_dashboard_to_db("title2", slug_1, owners=[admin])
        dashboard2_id = create_dashboard_to_db("title2", random_slug(), owners=[admin]).id

        self.login(username="admin")
        # Check for slug uniqueness
        dashboard_data = {"dashboard_title": "title2", "slug": slug_1}
        rv = self.update_dashboard(dashboard2_id, dashboard_data)
        self.assertStatus(rv, 422)
        response = json.loads(rv.data.decode("utf-8"))
        expected_response = {"message": {"slug": ["Must be unique"]}}
        self.assertEqual(response, expected_response)

    def test_update_dashboard_accept_empty_slug(self):

        admin = self.get_user("admin")
        title_ = random_title()
        dashboard2_id = create_dashboard_to_db(title_, None, owners=[admin]).id
        self.login(username="admin")
        # Accept empty slugs and don't validate them has unique
        dashboard_data = {"dashboard_title": "title2_changed", "slug": ""}
        rv = self.update_dashboard(dashboard2_id, dashboard_data)
        self.assert200(rv)

    @mark.update_name_error
    def test_update_dashboard_not_owned(self):
        """
        Dashboard API: Test update dashboard not owned
        """
        username = "alpha1"
        password = "password"
        user_alpha1 = self.create_user(
            username, password, "Alpha", email=f"{username}@superset.org"
        )

        alpha2 = "alpha2"
        self.create_user(
            alpha2, password, "Alpha", email=f"{alpha2}@superset.org"
        )

        existing_slice = (
            db.session.query(Slice).filter_by(slice_name="Girl Name Cloud").first()
        )
        dashboard_id = create_dashboard_to_db(random_title(), "slug1", published=True,
                                              owners=[user_alpha1],
                                              slices=[existing_slice]).id

        self.login(username=alpha2, password=password)
        dashboard_data = {
            "dashboard_title": random_title(),
            "slug": random_slug(),
        }
        rv = self.update_dashboard(dashboard_id, dashboard_data)
        self.assert403(rv)
        appbuilder.get_session.commit()

    def test_export(self):
        """
        Dashboard API: Test dashboard export
        """
        self.login(username="admin")
        argument = [1, 2]
        uri = EXPORT_DASHBOARDS_API_URL_WITH_QUERY_FORMAT.format(prison.dumps(argument))
        rv = self.get_assert_metric(uri, "export")
        self.assert200(rv)
        self.assertEqual(
            rv.headers["Content-Disposition"],
            generate_download_headers("json")["Content-Disposition"],
        )

    def test_export_not_found(self):
        """
        Dashboard API: Test dashboard export not found
        """
        self.login(username="admin")
        argument = [1000]
        uri = EXPORT_DASHBOARDS_API_URL_WITH_QUERY_FORMAT.format(prison.dumps(argument))
        rv = self.client.get(uri)
        self.assert404(rv)

    def test_export_not_allowed(self):
        """
        Dashboard API: Test dashboard export not allowed
        """
        admin = self.get_user("admin")
        dashboard = create_dashboard_to_db(random_title(), random_slug(),
                                           published=False, owners=[admin])

        self.login(username="gamma")
        argument = [dashboard.id]
        uri = EXPORT_DASHBOARDS_API_URL_WITH_QUERY_FORMAT.format(prison.dumps(argument))
        rv = self.client.get(uri)
        self.assert404(rv)

    def assert_dashboard_deleted(self, dashboard_id):
        model = get_dashboard_by_id(dashboard_id)
        self.assertEqual(model, None)
