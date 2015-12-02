# -*- coding: utf-8 -*-
#
#
#    Tech-Receptives Solutions Pvt. Ltd.
#    Copyright (C) 2009-TODAY Tech-Receptives(<http://www.techreceptives.com>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#

import logging
import urllib2
import xmlrpclib
import base64
from openerp import models, fields
from openerp.addons.connector.queue.job import job
from openerp.addons.connector.exception import MappingError
from openerp.addons.connector.unit.synchronizer import (Importer,
                                                        ExportSynchronizer
                                                        )
from openerp.addons.connector.event import on_record_create, on_record_write
from openerp.addons.connector.unit.mapper import (mapping,
                                                  ImportMapper,
                                                  ExportMapper
                                                  )
from openerp.addons.connector.exception import IDMissingInBackend
from ..unit.backend_adapter import (GenericAdapter)
from ..unit.import_synchronizer import (DelayedBatchImporter, WooImporter)
from ..unit.export_synchronizer import (WooExporter, export_record)
from ..connector import get_environment
from ..backend import woo

_logger = logging.getLogger(__name__)


class WooProductProduct(models.Model):
    _name = 'woo.product.product'
    _inherit = 'woo.binding'
    _inherits = {'product.product': 'openerp_id'}
    _description = 'woo product product'

    _rec_name = 'name'
    openerp_id = fields.Many2one(comodel_name='product.product',
                                 string='product',
                                 required=True,
                                 ondelete='cascade')
    backend_id = fields.Many2one(
        comodel_name='wc.backend',
        string='Woo Backend',
        store=True,
        readonly=False,
        required=False,
    )

    slug = fields.Char('Slung Name')
    credated_at = fields.Date('created_at')
    weight = fields.Float('weight')


class ProductProduct(models.Model):
    _inherit = 'product.product'

    woo_categ_ids = fields.Many2many(
        comodel_name='product.category',
        string='Woo product category',
    )
    woo_bind_ids = fields.One2many(
        comodel_name='woo.product.product',
        inverse_name='openerp_id',
        string="Woo Bindings",
    )
    in_stock = fields.Boolean('In Stock')


@woo
class ProductProductAdapter(GenericAdapter):
    _model_name = 'woo.product.product'
    _woo_model = 'products'

    def _call(self, url, arguments=False, method='get'):
        try:
            return super(ProductProductAdapter, self)._call(url, arguments=arguments, method=method)
        except xmlrpclib.Fault as err:
            # this is the error in the WooCommerce API
            # when the customer does not exist
            if err.faultCode == 102:
                raise IDMissingInBackend
            else:
                raise

    def search(self, filters=None, from_date=None, to_date=None):
        """ Search records according to some criteria and return a
        list of ids

        :rtype: list
        """
        if filters is None:
            filters = {}
        WOO_DATETIME_FORMAT = '%Y/%m/%d %H:%M:%S'
        dt_fmt = WOO_DATETIME_FORMAT
        if from_date is not None:
            # updated_at include the created records
            filters.setdefault('updated_at', {})
            filters['updated_at']['from'] = from_date.strftime(dt_fmt)
        if to_date is not None:
            filters.setdefault('updated_at', {})
            filters['updated_at']['to'] = to_date.strftime(dt_fmt)

        return self._call('products/list')

    def get_images(self, id, storeview_id=None):
        return self._call('products/' + str(id), [int(id), storeview_id, 'id'])

    def read_image(self, id, image_name, storeview_id=None):
        return self._call('products',
                          [int(id), image_name, storeview_id, 'id'])
        
    #def create(self, product):
    #    print('****pp')
    #    print(product)
    #    data = {
    #        'product': {
    #            'title': product.name
    #        }
    #    }
    #    return self.create(data)
        
    def export_quantity(self, filters, quantity):
        print('ok')
        data = {
            "product": {
                "title": "Premium Quality",
                "type": "simple",
                "regular_price": "21.99",
                "description": "Pellentesque habitant morbi tristique senectus et netus et malesuada fames ac turpis egestas. Vestibulum tortor quam, feugiat vitae, ultricies eget, tempor sit amet, ante. Donec eu libero sit amet quam egestas semper. Aenean ultricies mi vitae est. Mauris placerat eleifend leo.",
                "short_description": "Pellentesque habitant morbi tristique senectus et netus et malesuada fames ac turpis egestas.",
            }
        }
        print('ok2')
        return self.create(data)


@woo
class ProductBatchImporter(DelayedBatchImporter):

    """ Import the WooCommerce Partners.

    For every partner in the list, a delayed job is created.
    """
    _model_name = ['woo.product.product']

    def _import_record(self, woo_id, priority=None):
        """ Delay a job for the import """
        super(ProductBatchImporter, self)._import_record(
            woo_id, priority=priority)

    def run(self, filters=None):
        """ Run the synchronization """
#
        from_date = filters.pop('from_date', None)
        to_date = filters.pop('to_date', None)
        record_ids = self.backend_adapter.search(
            filters,
            from_date=from_date,
            to_date=to_date,
        )
        _logger.info('search for woo Products %s returned %s',
                     filters, record_ids)
        for record_id in record_ids:
            self._import_record(record_id, 30)


ProductBatchImporter = ProductBatchImporter


@woo
class ProductProductImporter(WooImporter):
    _model_name = ['woo.product.product']

    def _import_dependencies(self):
        """ Import the dependencies for the record"""
        record = self.woo_record
        record = record['product']
        for woo_category_id in record['categories']:
            self._import_dependency(woo_category_id,
                                    'woo.product.category')

    def _create(self, data):
        openerp_binding = super(ProductProductImporter, self)._create(data)
        return openerp_binding

    def _after_import(self, binding):
        """ Hook called at the end of the import """
        image_importer = self.unit_for(ProductImageImporter)
        image_importer.run(self.woo_id, binding.id)
        return

ProductProductImport = ProductProductImporter


@woo
class ProductImageImporter(Importer):

    """ Import images for a record.

    Usually called from importers, in ``_after_import``.
    For instance from the products importer.
    """
    _model_name = ['woo.product.product',
                   ]

    def _get_images(self, storeview_id=None):
        return self.backend_adapter.get_images(self.woo_id)

    def _sort_images(self, images):
        """ Returns a list of images sorted by their priority.
        An image with the 'image' type is the the primary one.
        The other images are sorted by their position.

        The returned list is reversed, the items at the end
        of the list have the higher priority.
        """
        if not images:
            return {}
        # place the images where the type is 'image' first then
        # sort them by the reverse priority (last item of the list has
        # the the higher priority)

    def _get_binary_image(self, image_data):
        url = image_data['src'].encode('utf8')
        url = str(url).replace("\\", '')
        try:
            request = urllib2.Request(url)
            binary = urllib2.urlopen(request)
        except urllib2.HTTPError as err:
            if err.code == 404:
                # the image is just missing, we skip it
                return
            else:
                # we don't know why we couldn't download the image
                # so we propagate the error, the import will fail
                # and we have to check why it couldn't be accessed
                raise
        else:
            return binary.read()

    def run(self, woo_id, binding_id):
        self.woo_id = woo_id
        images = self._get_images()
        images = images['product']
        images = images['images']
        binary = None
        while not binary and images:
            binary = self._get_binary_image(images.pop())
        if not binary:
            return
        model = self.model.with_context(connector_no_export=True)
        binding = model.browse(binding_id)
        binding.write({'image': base64.b64encode(binary)})


@woo
class ProductProductImportMapper(ImportMapper):
    _model_name = 'woo.product.product'

    direct = [
        ('description', 'description'),
        ('weight', 'weight'),
    ]

    @mapping
    def is_active(self, record):
        """Check if the product is active in Woo
        and set active flag in OpenERP
        status == 1 in Woo means active"""
        if record['product']:
            rec = record['product']
            return {'active': rec['visible']}

    @mapping
    def in_stock(self, record):
        if record['product']:
            rec = record['product']
            return {'in_stock': rec['in_stock']}

    @mapping
    def name(self, record):
        if record['product']:
            rec = record['product']
            return {'name': rec['title']}

    @mapping
    def type(self, record):
        if record['product']:
            rec = record['product']
            if rec['type'] == 'simple':
                return {'type': 'product'}

    @mapping
    def categories(self, record):
        if record['product']:
            rec = record['product']
            woo_categories = rec['categories']
            binder = self.binder_for('woo.product.category')
            category_ids = []
            main_categ_id = None
            for woo_category_id in woo_categories:
                cat_id = binder.to_openerp(woo_category_id, unwrap=True)
                if cat_id is None:
                    raise MappingError("The product category with "
                                       "woo id %s is not imported." %
                                       woo_category_id)
                category_ids.append(cat_id)
            if category_ids:
                main_categ_id = category_ids.pop(0)
            result = {'woo_categ_ids': [(6, 0, category_ids)]}
            if main_categ_id:  # OpenERP assign 'All Products' if not specified
                result['categ_id'] = main_categ_id
            return result

    @mapping
    def price(self, record):
        """ The price is imported at the creation of
        the product, then it is only modified and exported
        from OpenERP """
        if record['product']:
            rec = record['product']
            return {'list_price': rec and rec['price'] or 0.0}

    @mapping
    def sale_price(self, record):
        """ The price is imported at the creation of
        the product, then it is only modified and exported
        from OpenERP """
        if record['product']:
            rec = record['product']
            return {'standard_price': rec and rec['sale_price'] or 0.0}

    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}


@woo
class ProductProductExport(WooExporter):
    _model_name = ['woo.product.product']
    _data_key = 'product'
#
#    def get_filter(self, product):
#        binder = self.get_binder_for_model()
#        prestashop_id = binder.to_backend(product.id)
#        return {
#            'filter[id_product]': prestashop_id,
#            'filter[id_product_attribute]': 0
#        }

    #def run(self, binding_id, fields):
    #    """ ZZZ """
    #    product = self.session.browse(self.model._name, binding_id)
    #    print('-----')
    #    print(product)
    #    print('-----')
    #    adapter = self.get_connector_unit_for_model(
    #        GenericAdapter, 'woo.product.product'
    #    )
    #    #filter = self.get_filter(product)
    #    #filter  = 5
    #    #adapter.export_quantity(filter, product.name)
    #    adapter.create(product)
    
    #def _create_data(self, map_record, fields=None, **kwargs):
    #    """ Get the data to pass to :py:meth:`_create` """
    #    print('dans create data')
    #    print(self._data_key)
    #    data = map_record.values(for_create=True, fields=fields, **kwargs)
    #    return {'product': data}
    
    #def _create(self, data):
    #    """ Create the Magento record """
    #    # special check on data before export
    #    self._validate_create_data(data)
   #     result = self.backend_adapter.create(data)
     #   return result['product']['id']
        
        
@woo
class ProductProductExportMapper(ExportMapper):
    _model_name = 'woo.product.product'

    direct = [
        ('name', 'title'),
        ('list_price', 'regular_price')
    ]

@job(default_channel='root.woo')
def product_import_batch(session, model_name, backend_id, filters=None):
    """ Prepare the import of product modified on Woo """
    if filters is None:
        filters = {}
    env = get_environment(session, model_name, backend_id)
    importer = env.get_connector_unit(ProductBatchImporter)
    importer.run(filters=filters)
    














@on_record_create(model_names='product.product')
def product_create_bindings(session, model_name, record_id, vals):
    """
    Create a ``magento.account.invoice`` record. This record will then
    be exported to Magento.
    """
    print('CREATE PRODUCT')
    session.env['woo.product.product'].create({
        'backend_id': 1,
        'openerp_id': record_id})
    
    
@on_record_write(model_names='product.product')
def product_write_bindings(session, model_name, record_id, vals):
    """
    Create a ``magento.account.invoice`` record. This record will then
    be exported to Magento.
    """
    print('WRITE PRODUCT')
    print(vals)
    delay_export_all_bindings(session, model_name, record_id, vals)

@on_record_create(model_names='woo.product.product')
def delay_export_product_product(session, model_name, record_id, vals):
    """
    Delay the job to export the magento invoice.
    """
    print('CREATE WOO PRODUCT')
    delay_export(session, model_name, record_id, vals)

def delay_export(session, model_name, record_id, vals):
    """ Delay a job which export a binding record.
    (A binding record being a ``magento.res.partner``,
    ``magento.product.product``, ...)
    """
    if session.context.get('connector_no_export'):
        return
    fields = vals.keys()
    print('delay_export')
    print(fields)
    export_record.delay(session, model_name, record_id, fields=fields)
    
def delay_export_all_bindings(session, model_name, record_id, vals):
    """ Delay a job which export all the bindings of a record.
    In this case, it is called on records of normal models and will delay
    the export for all the bindings.
    """
    if session.context.get('connector_no_export'):
        return
    record = session.env[model_name].browse(record_id)
    fields = vals.keys()
    print('delay_export_all_bindings')
    print(fields)
    for binding in record.woo_bind_ids:
        export_record.delay(session, binding._model._name, binding.id,
                            fields=fields)






















#@job(default_channel='root.woo')
#def export_product(session, model_name, record_id, fields=None):
#    """ Export a validated or paid invoice. """
#    product = session.env[model_name].browse(record_id)
#    print(fields)
#    print(product)
#    backend_id = product.backend_id.id
#    print(backend_id)
#    env = get_environment(session, model_name, backend_id)
#    exporter = env.get_connector_unit(ProductProductExport)
#    return exporter.run(record_id, fields)




    
@job(default_channel='root.woo')
def product_export_batch(session, model_name, record_id, fields=None):
    """ ZZZ """
    print(record_id)
    print(model_name)
    product = session.browse(model_name, record_id)
    backend_id = product.backend_id.id
    env = get_environment(session, model_name, backend_id)
    exporter = env.get_connector_unit(ProductProductExport)
    return exporter.run(record_id, fields)
