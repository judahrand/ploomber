"""
Tests remote metadata bulk download during DAG.render
"""
from glob import glob
from pathlib import Path
from unittest.mock import Mock

import pytest

from ploomber import DAG
from ploomber.products import File, SQLiteRelation
from ploomber.clients import LocalStorageClient, SQLAlchemyClient
from ploomber.tasks import PythonCallable, SQLScript
from ploomber.executors import Serial
from ploomber.dag import DAG as dag_module
from ploomber.exceptions import DAGRenderError


def touch_root(product):
    Path(product).touch()


def touch_root_metaproduct(product):
    for p in product:
        Path(p).touch()


@pytest.fixture
def dag():
    dag = DAG(executor=Serial(build_in_subprocess=False))
    dag.clients[File] = LocalStorageClient('remote', path_to_project_root='.')
    PythonCallable(touch_root, File('one'), dag=dag)
    return dag


@pytest.fixture
def dag_w_error():
    dag = DAG(executor=Serial(build_in_subprocess=False))
    dag.clients[File] = LocalStorageClient('remote', path_to_project_root='.')
    PythonCallable(touch_root, File('one'), dag=dag, params=dict(a=1))
    return dag


def test_calls_parallel_download(tmp_directory, monkeypatch, dag):
    dag.build()
    mock = Mock(wraps=dag_module.fetch_remote_metadata_in_parallel)
    monkeypatch.setattr(dag_module, 'fetch_remote_metadata_in_parallel', mock)
    # mock_remote = Mock(wraps=file._RemoteFile)
    # monkeypatch.setattr(file, '_RemoteFile', mock_remote)

    dag.render()

    # TODO: check files are actually there when inside the context
    mock.assert_called_once_with(dag)

    # mock_remote.assert_called_once()

    # should clean up remote copies
    assert not glob('*.metadata.remote')


def test_cleans_up_files_if_render_fails(dag_w_error):
    with pytest.raises(DAGRenderError):
        dag_w_error.render()

    assert not glob('*.metadata.remote')


def test_ignores_non_file_products(tmp_directory):
    client = SQLAlchemyClient('sqlite:///my.db')

    dag = DAG()
    dag.clients[SQLScript] = client
    dag.clients[SQLiteRelation] = client
    dag.clients[File] = LocalStorageClient('remote', path_to_project_root='.')

    SQLScript('CREATE TABLE {{product}} AS SELECT * FROM data',
              SQLiteRelation(['data2', 'table']),
              dag=dag,
              name='task')

    dag.render()

    client.close()


def tes_processes_metaproducts(tmp_directory, monkeypatch):
    dag = DAG(executor=Serial(build_in_subprocess=False))
    dag.clients[File] = LocalStorageClient('remote', path_to_project_root='.')
    PythonCallable(touch_root_metaproduct, {
        'one': File('one'),
        'two': File('two')
    },
                   dag=dag)
    dag.build()

    mock = Mock(wraps=dag_module.fetch_remote_metadata_in_parallel)
    monkeypatch.setattr(dag_module, 'fetch_remote_metadata_in_parallel', mock)

    dag.render()

    mock.assert_called_once_with(dag)

    # should clean up remote copies
    assert not glob('*.metadata.remote')


def test_dag_without_client(monkeypatch, tmp_directory):
    mock = Mock(wraps=dag_module.fetch_remote_metadata_in_parallel)
    monkeypatch.setattr(dag_module, 'fetch_remote_metadata_in_parallel', mock)

    dag = DAG(executor=Serial(build_in_subprocess=False))
    PythonCallable(touch_root, File('one'), dag=dag)

    dag.render()

    # should call it but nothing will happen
    mock.assert_called_once_with(dag)


# TODO: mock remote file to ensure _fetch_metadata is called on each
# TODO: test metaproducts with mixed files and non files?
# TODO: test mixed inside a metaproduct
# TODO: do some testing with gcp client - see if it's thread safe