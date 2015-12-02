# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (c) 2013 LogicaSoft SPRL (<http://www.logicasoft.eu>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from openerp.addons.connector.queue.job import job, related_action
from openerp.addons.connector.unit.synchronizer import Exporter
from ..connector import get_environment
from ..related_action import link


class WooBaseExporter(Exporter):

    """ Base exporter for WooCommerce """

    def __init__(self, connector_env):
        """
        :param connector_env: current environment (backend, session, ...)
        :type connector_env: :class:`connector.connector.ConnectorEnvironment`
        """
        super(WooBaseExporter, self).__init__(connector_env)
        self.binding_id = None
        self.woo_id = None
        
    def _get_openerp_data(self):
        """ Return the raw OpenERP data for ``self.binding_id`` """
        return self.model.browse(self.binding_id)
    
    def run(self, binding_id, *args, **kwargs):
        """ Run the synchronization
        :param binding_id: identifier of the binding record to export
        """
        self.binding_id = binding_id
        self.binding_record = self._get_openerp_data()

        self.woo_id = self.binder.to_backend(self.binding_id)
        result = self._run(*args, **kwargs)

        self.binder.bind(self.woo_id, self.binding_id)
        return result
    
    def _run(self):
        """ Flow of the synchronization, implemented in inherited classes"""
        raise NotImplementedError
    
    
class WooExporter(WooBaseExporter):
    """ A common flow for the exports to WooCommerce """

    def __init__(self, connector_env):
        """
        :param connector_env: current environment (backend, session, ...)
        :type connector_env: :class:`connector.connector.ConnectorEnvironment`
        """
        super(WooExporter, self).__init__(connector_env)
        self.binding_record = None
        
    def _has_to_skip(self):
        """ Return True if the export can be skipped """
        return False
    
    def _map_data(self):
        """ Returns an instance of
        :py:class:`~openerp.addons.connector.unit.mapper.MapRecord`
        """
        return self.mapper.map_record(self.binding_record)
    
    def _validate_create_data(self, data):
        """ Check if the values to import are correct
        Pro-actively check before the ``Model.create`` if some fields
        are missing or invalid
        Raise `InvalidDataError`
        """
        return
    
    def _validate_update_data(self, data):
        """ Check if the values to import are correct
        Pro-actively check before the ``Model.update`` if some fields
        are missing or invalid
        Raise `InvalidDataError`
        """
        return
    
    def _create_data(self, map_record, fields=None, **kwargs):
        """ Get the data to pass to :py:meth:`_create` """
        data = map_record.values(for_create=True, fields=fields, **kwargs)
        return {self._data_key : data}
    
    def _create(self, data):
        """ Create the Magento record """
        # special check on data before export
        self._validate_create_data(data)
        result = self.backend_adapter.create(data)
        return result[self._data_key]['id']
    
    def _update_data(self, map_record, fields=None, **kwargs):
        """ Get the data to pass to :py:meth:`_update` """
        data = map_record.values(fields=fields, **kwargs)
        return {self._data_key : data}

    def _update(self, data):
        """ Update an Magento record """
        assert self.woo_id
        # special check on data before export
        self._validate_update_data(data)
        print('///////////')
        print('_update')
        print(data)
        print('///////////')
        self.backend_adapter.write(self.woo_id, data)
        
    def _run(self, fields=None):
        """ Flow of the synchronization, implemented in inherited classes"""
        assert self.binding_id
        assert self.binding_record
        print('ooooo')
        if not self.woo_id:
            fields = None  # should be created with all the fields

        if self._has_to_skip():
            return

        # export the missing linked resources
        #TODOself._export_dependencies()

        # prevent other jobs to export the same record
        # will be released on commit (or rollback)
        #TODOself._lock()

        map_record = self._map_data()
        print(map_record)

        if self.woo_id:
            record = self._update_data(map_record, fields=fields)
            if not record:
                return _('Nothing to export.')
            self._update(record)
        else:
            record = self._create_data(map_record, fields=fields)
            print('77777')
            print(record)
            if not record:
                return _('Nothing to export.')
            self.woo_id = self._create(record)
        return _('Record exported with ID %s on Magento.') % self.woo_id


@job(default_channel='root.woo')
#@related_action(action=unwrap_binding)
def export_record(session, model_name, binding_id, fields=None):
    """ Export a record on WooCommerce """
    record = session.env[model_name].browse(binding_id)
    env = get_environment(session, model_name, record.backend_id.id)
    exporter = env.get_connector_unit(WooExporter)
    return exporter.run(binding_id, fields=fields)
