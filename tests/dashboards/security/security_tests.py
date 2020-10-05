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
"""Unit tests for Superset"""

from flask import escape
import json
import prison
from pytest import mark
from random import random
from superset.models import core as models
from tests.dashboards.base_case import DashboardTestCase
from tests.dashboards.consts import *
from tests.dashboards.dashboard_test_utils import *
from tests.dashboards.superset_factory_util import *

@mark.skipif(
    is_dashboard_level_access_enabled(),
    reason="with dashboard level access favorite by itself will not permit access to the dashboard",
)
class TestDashboardSecurity(DashboardTestCase):

    def test_dashboard_access__admin_can_access_all(self):
        # arrange
        self.login(username=ADMIN_USERNAME)
        dashboard_title_by_url = {
            dash.url: dash.dashboard_title for dash in get_all_dashboards()
        }

        # act
        responses_by_url = {
            url: self.client.get(url).data.decode("utf-8")
            for url in dashboard_title_by_url.keys()
        }

        # assert
        for dashboard_url, get_dashboard_response in responses_by_url.items():
            assert (
                escape(dashboard_title_by_url[dashboard_url]) in get_dashboard_response
            )

    def test_dashboard_access_with_created_by_can_be_accessed_by_public_users(self):
        # arrange
        self.logout()
        the_accessed_table_name = DEFAULT_ACCESSIBLE_TABLE
        the_accessed_dashboard_slug = DASHBOARD_SLUG_OF_ACCESSIBLE_TABLE
        table_to_access = get_sql_table_by_name(the_accessed_table_name)
        dashboard_to_access = get_dashboard_by_slug(the_accessed_dashboard_slug)
        original_owners = dashboard_to_access.owners
        original_created_by = dashboard_to_access.created_by
        admin_user = security_manager.find_user(ADMIN_USERNAME)
        dashboard_to_access.owners = [admin_user]
        dashboard_to_access.created_by = admin_user
        db.session.merge(dashboard_to_access)
        db.session.commit()
        self.grant_public_access_to_table(table_to_access)

        # act
        get_dashboard_response = self.get_resp(dashboard_to_access.url)
        try:
            # assert
            assert dashboard_to_access.dashboard_title in get_dashboard_response
        finally:
            # post test - bring back owner and created_by
            self.revoke_public_access_to_table(table_to_access)
            self.login(username=ADMIN_USERNAME)
            dashboard_to_access.owners = original_owners
            dashboard_to_access.created_by = original_created_by
            db.session.merge(dashboard_to_access)
            db.session.commit()

    def test_dashboard_access_in_edit_and_standalone_modes(self):
        # arrange
        self.login(username=ADMIN_USERNAME)
        dash = get_dashboard_by_slug(DEFAULT_DASHBOARD_SLUG_TO_TEST)
        dashboard_url_with_modes = self.__add_dashboard_mode_parmas(dash.url)

        # act
        resp = self.get_resp(dashboard_url_with_modes)

        # assert
        self.assertIn("editMode&#34;: true", resp)
        self.assertIn("standalone_mode&#34;: true", resp)
        self.assertIn('<body class="standalone">', resp)

    def test_get_dashboards__users_are_dashboards_owners(self):
        # arrange
        username = "gamma"
        user = security_manager.find_user(username)
        my_owned_dashboard = create_dashboard_to_db(dashboard_title="My Dashboard",
                                                    slug=f"my_dash_{random()}",
                                                    published=False, owners=[user.id])

        not_my_owned_dashboard = create_dashboard_to_db(
            dashboard_title="Not My Dashboard", slug=f"not_my_dash_{random()}",
            published=False)

        self.login(user.username)

        # act
        get_dashboards_response = self.get_resp(DASHBOARDS_API_URL)

        # assert
        self.assertIn(my_owned_dashboard.url, get_dashboards_response)
        self.assertNotIn(not_my_owned_dashboard.url, get_dashboards_response)

    def test_get_dashboards__owners_can_view_empty_dashboard(self):
        # arrange
        dash = create_dashboard_to_db("Empty Dashboard", slug="empty_dashboard")
        dashboard_url = dash.url
        gamma_user = security_manager.find_user("gamma")
        self.login(gamma_user.username)

        # act
        get_dashboards_response = self.get_resp(DASHBOARDS_API_URL)

        # assert
        self.assertNotIn(dashboard_url, get_dashboards_response)

    def test_get_dashboards__users_can_view_favorites_dashboards(self):
        # arrange
        user = security_manager.find_user("gamma")
        fav_dash_slug = f"my_favorite_dash_{random()}"
        regular_dash_slug = f"regular_dash_{random()}"

        favorite_dash = Dashboard()
        favorite_dash.dashboard_title = "My Favorite Dashboard"
        favorite_dash.slug = fav_dash_slug

        regular_dash = Dashboard()
        regular_dash.dashboard_title = "A Plain Ol Dashboard"
        regular_dash.slug = regular_dash_slug

        db.session.merge(favorite_dash)
        db.session.merge(regular_dash)
        db.session.commit()

        dash = db.session.query(Dashboard).filter_by(slug=fav_dash_slug).first()

        favorites = models.FavStar()
        favorites.obj_id = dash.id
        favorites.class_name = "Dashboard"
        favorites.user_id = user.id

        db.session.merge(favorites)
        db.session.commit()

        self.login(user.username)

        # act
        get_dashboards_response = self.get_resp(DASHBOARDS_API_URL)

        # assert
        self.assertIn(f"/superset/dashboard/{fav_dash_slug}/", get_dashboards_response)

    def test_get_dashboards__user_can_not_view_unpublished_dash(self):
        # arrange
        admin_user = security_manager.find_user(ADMIN_USERNAME)
        gamma_user = security_manager.find_user(GAMMA_USERNAME)
        slug = f"admin_owned_unpublished_dash_{random()}"

        admin_and_not_published_dashboard = create_dashboard_to_db("My Dashboard",
                                                                   slug=slug,
                                                                   owners=[admin_user])

        self.login(gamma_user.username)

        # act - list dashboards as a gamma user
        get_dashboards_response_as_gamma = self.get_resp(DASHBOARDS_API_URL)

        # assert
        self.assertNotIn(
            admin_and_not_published_dashboard.url, get_dashboards_response_as_gamma
        )

    def test_save_dash__only_owners_can_save(self):
        # arrange
        dashboard_to_be_saved = get_dashboard_by_slug(DEFAULT_DASHBOARD_SLUG_TO_TEST)
        alpha_user = security_manager.find_user(ALPHA_USERNAME)

        # arrange before #1
        dashboard_to_be_saved.owners = []
        db.session.merge(dashboard_to_be_saved)
        db.session.commit()
        self.logout()

        # act + assert #1
        self.assertRaises(Exception, self.save_dash_basic_case, ALPHA_USERNAME)

        # arrange before call #2
        dashboard_to_be_saved.owners = [alpha_user]
        db.session.merge(dashboard_to_be_saved)
        db.session.commit()

        # act #2
        self.save_dash_basic_case(alpha_user)

    def test_get_dashboards__public_user_get_published(self):
        # arrange #1
        dashboard_level_access_enabled = (
            is_dashboard_level_access_enabled()
        )
        the_accessed_table_name = "birth_names"
        not_accessed_table_name = "wb_health_population"
        the_accessed_dashboard_slug = "births"
        the_not_accessed_dashboard_slug = "world_health"
        table_to_access = get_sql_table_by_name(the_accessed_table_name)
        dashboard_to_access = get_dashboard_by_slug(the_accessed_dashboard_slug)
        # Make the births dash published so it can be seen
        published_value_of_accessed_dashboard = dashboard_to_access.published
        dashboard_to_access.published = True
        url_of_the_accessed_dashboard = dashboard_to_access.url
        title_of_the_access_dashboard = dashboard_to_access.dashboard_title
        db.session.merge(dashboard_to_access)

        dashboard_not_to_access = get_dashboard_by_slug(the_not_accessed_dashboard_slug)
        published_value_of_not_accessed_dashboard = dashboard_not_to_access.published
        dashboard_not_to_access.published = False
        url_of_not_accessed_dashboard = dashboard_not_to_access.url
        db.session.merge(dashboard_to_access)
        db.session.commit()

        self.revoke_public_access_to_table(table_to_access)
        self.logout()

        # act #1 - Try access before adding appropriate permissions
        get_charts_response = self.get_resp(GET_CHARTS_API_URL)
        get_dashboards_response = self.get_resp(DASHBOARDS_API_URL)

        # assert #1
        self.assertNotIn(the_accessed_table_name, get_charts_response)
        self.assertNotIn(url_of_the_accessed_dashboard, get_dashboards_response)

        # arrange #2 - grant permissions
        self.grant_public_access_to_table(table_to_access)

        try:
            # act #2 - Try access after adding appropriate permissions.
            get_charts_response = self.get_resp(GET_CHARTS_API_URL)
            get_dashboards_response = self.get_resp(DASHBOARDS_API_URL)

            # assert #2
            self.assertIn(the_accessed_table_name, get_charts_response)
            self.assertIn(url_of_the_accessed_dashboard, get_dashboards_response)
            self.assertIn(
                title_of_the_access_dashboard,
                self.get_resp(url_of_the_accessed_dashboard),
            )
            self.assertNotIn(not_accessed_table_name, get_charts_response)
            self.assertNotIn(url_of_not_accessed_dashboard, get_dashboards_response)

        finally:
            do_commit = False
            if published_value_of_not_accessed_dashboard:
                dashboard_not_to_access.published = True
                db.session.merge(dashboard_not_to_access)
                do_commit = True
            if not published_value_of_accessed_dashboard:
                dashboard_to_access.published = False
                db.session.merge(dashboard_to_access)
                do_commit = True
            if do_commit:
                db.session.commit()
            self.revoke_public_access_to_table(table_to_access)

    def test_get_dashboards__users_can_view_permitted_dashboard(self):
        # arrange
        dashboard_level_access_enabled = (
            is_dashboard_level_access_enabled()
        )
        accessed_table = get_sql_table_by_name("energy_usage")
        self.grant_role_access_to_table(accessed_table, GAMMA_ROLE_NAME)
        # get a slice from the allowed table
        slice_to_add_to_dashboards = get_slice_by_name("Energy Sankey")
        # Create a published and hidden dashboard and add them to the database
        first_dash = create_dashboard_to_db(dashboard_title="Published Dashboard",
                                            slug=f"first_dash_{random()}",
                                            published=True,
                                            slices=[slice_to_add_to_dashboards])

        second_dash = create_dashboard_to_db(dashboard_title="Hidden Dashboard",
                                             slug=f"second_dash_{random()}",
                                             published=True,
                                             slices=[slice_to_add_to_dashboards])

        try:
            self.login(GAMMA_USERNAME)
            # act
            get_dashboards_response = self.get_resp(DASHBOARDS_API_URL)

            # assert
            self.assertIn(second_dash.url, get_dashboards_response)
            self.assertIn(first_dash.url, get_dashboards_response)
        finally:
            self.revoke_public_access_to_table(accessed_table)

    @staticmethod
    def __add_dashboard_mode_parmas(dashboard_url):
        full_url = dashboard_url
        if dashboard_url.find("?") == -1:
            full_url += "?"
        else:
            full_url += "&"
        return full_url + "edit=true&standalone=true"

    def test_get_dashboard_api_no_data_access(self):
        """
        Dashboard API: Test get dashboard without data access
        """
        admin = self.get_user("admin")
        dashboard = create_dashboard_to_db(random_title(), random_slug(), owners=[admin])

        self.login(username="gamma")
        uri = DASHBOARD_API_URL_FORMAT.format(dashboard.id)
        rv = self.client.get(uri)
        self.assert404(rv)

    def test_get_dashboards_api_no_data_access(self):
        """
        Dashboard API: Test get dashboards no data access
        """
        admin = self.get_user("admin")
        title = f"title{random_str()}"
        create_dashboard_to_db(title, "slug1", owners=[admin])

        self.login(username="gamma")
        arguments = {
            "filters": [{"col": "dashboard_title", "opr": "sw", "value": title[0:8]}]
        }
        uri = DASHBOARDS_API_URL_WITH_QUERY_FORMAT.format(prison.dumps(arguments))
        rv = self.client.get(uri)
        self.assert200(rv)
        data = json.loads(rv.data.decode("utf-8"))
        self.assertEqual(0, data["count"])
