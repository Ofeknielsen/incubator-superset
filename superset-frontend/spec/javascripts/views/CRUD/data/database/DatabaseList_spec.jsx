/**
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */
import React from 'react';
import thunk from 'redux-thunk';
import configureStore from 'redux-mock-store';
import { styledMount as mount } from 'spec/helpers/theming';

import DatabaseList from 'src/views/CRUD/data/database/DatabaseList';
import DatabaseModal from 'src/views/CRUD/data/database/DatabaseModal';
import SubMenu from 'src/components/Menu/SubMenu';

// store needed for withToasts(DatabaseList)
const mockStore = configureStore([thunk]);
const store = mockStore({});

describe('DatabaseList', () => {
  const wrapper = mount(<DatabaseList />, { context: { store } });

  it('renders', () => {
    expect(wrapper.find(DatabaseList)).toExist();
  });

  it('renders a SubMenu', () => {
    expect(wrapper.find(SubMenu)).toExist();
  });

  it('renders a DatabaseModal', () => {
    expect(wrapper.find(DatabaseModal)).toExist();
  });
});
